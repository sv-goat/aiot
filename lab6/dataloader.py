import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from pathlib import Path

HAR_LABELS = {
    1: "WALKING",
    2: "WALKING_UPSTAIRS",
    3: "WALKING_DOWNSTAIRS",
    4: "SITTING",
    5: "STANDING",
    6: "LAYING"
}

CHANNEL_SETS = [
    "total_acc_x_{split}.txt",
    "total_acc_y_{split}.txt",
    "total_acc_z_{split}.txt",
    "body_gyro_x_{split}.txt",
    "body_gyro_y_{split}.txt",
    "body_gyro_z_{split}.txt",
]


class UCIHARSignals(Dataset):
    """
    Returns for __getitem__(i):body_gyro_z_
      x: torch.FloatTensor with shape [C, L] (channels-first for Conv1d)
      y: int in [0..5]
      y_name: str (human-readable)
    """

    def __init__(self, root, split="train"):
        base = Path(root) / split / "Inertial Signals"

        # Load and stack all channel data -> shape [N, C, L]
        channels = []
        for cfile in CHANNEL_SETS:
            path = base / cfile.format(split=split)
            data = np.loadtxt(path)  # [N, L]
            channels.append(data)
        x = np.stack(channels, axis=1)  # -> [N, C, L]

        # Normalize per channel (zero mean, unit variance)
        mean = x.mean(axis=(0, 2), keepdims=True)
        std = x.std(axis=(0, 2), keepdims=True)
        x = (x - mean) / (std + 1e-8)

        self.x = torch.tensor(x, dtype=torch.float32)

        # Load labels and map from [1..6] to [0..5]
        y_path = Path(root) / split / "y_{split}.txt".format(split=split)
        y = np.loadtxt(y_path, dtype=int) - 1
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        x = self.x[i]          # [C, 128]
        y = self.y[i].item()   # scalar in [0..5]
        y_name = HAR_LABELS[y + 1]
        return x, y, y_name

if __name__ == "__main__":
    data_dir = "/Users/srira/Desktop/College_Assignments/Columbia/Fall_2025/AIOT/Lab_6/human+activity+recognition+using+smartphones/UCI_HAR_Dataset"
    train_loader = DataLoader(UCIHARSignals(data_dir, "train"), batch_size=32, shuffle=True)
    xb, yb, yname = next(iter(train_loader))
    print("x:", xb.shape)  # [B, C, L], e.g. [32, 6, 128]
    print("y:", yb.shape)  # [B]
    print("names:", yname[:3])
