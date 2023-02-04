import json


def write_to_file(filename, data: dict):
    json_formatted_str = json.dumps(data, indent=4)
    f = open(filename, "w")
    f.write(json_formatted_str)
    f.close()
