import json

def save(dict, backup_copy=False):
    '''Saves selected dictionary as Data.json'''
    file_name = "Version2.0\Data\Data Bank\Data.json"
    with open(file_name, "w") as out:
        json_object = json.dumps(dict, indent=4)
        out.write(json_object)

    if backup_copy:
        backup_file_name = "Version2.0\Data\Data Bank\Backup_Data.json"
        with open(backup_file_name, "w") as out:
            json_object = json.dumps(dict, indent=4)
            out.write(json_object)