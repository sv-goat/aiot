import asyncio
import random
import numpy as np
import torch
from torch.utils.data import Dataset
from pathlib import Path
import fastapi_poe as fp

# ======================================================
# 1️⃣ Poe API setup
# ======================================================
poe_api_key = "sEIxZsHJyHVpSZh3WjCzOGqnitGyaGXzoUz_Ls2oJ64"

async def get_llm_response(prompt: str):
    """Send a single prompt to GPT-4o-Mini via Poe and return full response."""
    message = fp.ProtocolMessage(role="user", content=prompt)
    full_response = ""
    async for partial in fp.get_bot_response(
        messages=[message],
        bot_name="GPT-4o-Mini",
        api_key=poe_api_key
    ):
        full_response += partial.text
    return full_response.strip()

# ======================================================
# 2️⃣ Dataset Definition (UCI HAR)
# ======================================================
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
    Returns for __getitem__(i):
      x: torch.FloatTensor with shape [C, L]
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

        # Normalize per channel
        mean = x.mean(axis=(0, 2), keepdims=True)
        std = x.std(axis=(0, 2), keepdims=True)
        x = (x - mean) / (std + 1e-8)
        self.x = torch.tensor(x, dtype=torch.float32)

        # Load labels
        y_path = Path(root) / split / f"y_{split}.txt"
        y = np.loadtxt(y_path, dtype=int) - 1
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        x = self.x[i]          # [C, 128]
        y = self.y[i].item()   # scalar in [0..5]
        y_name = HAR_LABELS[y + 1]
        return x, y, y_name

# ======================================================    
# 3️⃣ CoT vs Direct Evaluation
# ======================================================
async def classify_sample(x_tensor, y_true_name):
    """Send CoT and Direct prompts to the LLM for one test sample."""
    x_np = x_tensor.numpy()
    flattened = x_np.flatten(order='F')  # Flatten in column-major order so that we send info from all channels over time
    sample_vals = ", ".join([f"{v:.2f}" for v in flattened[:30]]) + " ..."
    candidate_labels = ", ".join(HAR_LABELS.values())

    base_prompt = f"""
Device: Smartphone
Attached Location: Waist
Candidate Activities: {{{candidate_labels}}}
Data (Accelerometer x, y, z  Gyroscope x, y, z signals over time): [{sample_vals}]
Question: Which activity is being performed?
"""

    cot_prompt = base_prompt + " Explain your reasoning step by step, then give the activity label."
    direct_prompt = base_prompt + " Give only the activity label."

    cot_response = await get_llm_response(cot_prompt)
    direct_response = await get_llm_response(direct_prompt)

    return {
        "true_label": y_true_name,
        "cot_response": cot_response,
        "direct_response": direct_response,
    }

async def main():
    DATA_DIR = "/Users/srira/Desktop/College_Assignments/Columbia/Fall_2025/AIOT/Lab_6/human+activity+recognition+using+smartphones/UCI_HAR_Dataset"
    dataset = UCIHARSignals(DATA_DIR, split="test")
    indices = random.sample(range(len(dataset)), 100)

    results = []
    correct_cot = correct_direct = consistent = 0

    print("\nRunning LLM inference on 10 random test samples...\n")

    for idx in indices:
        x, _, y_name = dataset[idx]
        print(f"🧩 Sample {idx} | True label: {y_name}")
        res = await classify_sample(x, y_name)
        results.append(res)

        cot_pred = next((lbl for lbl in HAR_LABELS.values() if lbl in res["cot_response"].upper()), None)
        direct_pred = next((lbl for lbl in HAR_LABELS.values() if lbl in res["direct_response"].upper()), None)

        if cot_pred == y_name:
            correct_cot += 1
        if direct_pred == y_name:
            correct_direct += 1
        if cot_pred == direct_pred:
            consistent += 1

        print(f"  CoT Prediction: {cot_pred or '???'}")
        print(f"  Direct Prediction: {direct_pred or '???'}\n")

    acc_cot = correct_cot / len(indices) * 100
    acc_direct = correct_direct / len(indices) * 100
    consistency = consistent / len(indices) * 100

    print("=" * 60)
    print("🔍 SUMMARY")
    print(f"Chain-of-Thought Accuracy: {acc_cot:.1f}%")
    print(f"Direct Answer Accuracy:   {acc_direct:.1f}%")
    print(f"Label Consistency:         {consistency:.1f}%")
    print("=" * 60)

    # print("\nSampled Responses:\n")
    # for i, r in enumerate(results, 1):
    #     print(f"#{i}. True: {r['true_label']}")
    #     print(f"   CoT: {r['cot_response']}")
    #     print(f"   Direct: {r['direct_response']}\n")

if __name__ == "__main__":
    asyncio.run(main())
