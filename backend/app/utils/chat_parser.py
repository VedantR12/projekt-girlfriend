import re

def parse_chat(text_data: str):
    lines = text_data.split("\n")

    messages = []

    # WhatsApp pattern:
    # 12/04/23, 10:38 pm - Name: Message
    pattern = r"^\d{1,2}/\d{1,2}/\d{2,4},\s.*?-\s(.*?):\s(.*)$"

    for line in lines:
        line = line.strip()

        if not line:
            continue

        match = re.match(pattern, line)

        if match:
            name = match.group(1).strip()
            message = match.group(2).strip()

            if not message:
                continue

            messages.append({
                "speaker": name,
                "text": message
            })

    return messages