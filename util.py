import json

from constant import DISCORD_COMMAND


def write_to_file(filename, data: dict):
    json_formatted_str = json.dumps(data, indent=4)
    f = open(filename, "w")
    f.write(json_formatted_str)
    f.close()


def get_command(input: str):
    t = input.strip()
    t = remove_prefix(t, DISCORD_COMMAND)
    t = t.strip()
    return t.split(" ")


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text
