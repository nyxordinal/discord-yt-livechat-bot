import json


def write_to_file(filename, data: dict):
    json_formatted_str = json.dumps(data, indent=4)
    f = open(filename, "w")
    f.write(json_formatted_str)
    f.close()


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    return text
