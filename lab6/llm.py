# poe_inference.py
# verify_poe_api.py
import asyncio
import fastapi_poe as fp

poe_api_key = "sEIxZsHJyHVpSZh3WjCzOGqnitGyaGXzoUz_Ls2oJ64"

async def get_llm_response(prompt):
    message = fp.ProtocolMessage(role="user", content=prompt)
    full_response = ""
    async for partial in fp.get_bot_response(messages=[message],
    bot_name='GPT-4o-Mini',
    api_key=poe_api_key):
        full_response += partial.text
    return full_response

if __name__ == "__main__":
    prompt = """
        Device: Smartphone
        Attached Location: {}
        Candidate Activities: {walking, sitting, ...}
        Data (Accelerometer X,Y,Z over time): [0.3, -0.1, ...]
        Question: Which activity is being performed?
    """

    llm_response = asyncio.run(get_llm_response(prompt))
    print(f"LLM Response: {llm_response}")

