class BoxFile:
    def __init__(self, id: str, name: str, file_version_id: str, sha1: str):
        self.id = id
        self.name = name
        self.file_version_id = file_version_id
        self.sha1 = sha1

    def __str__(self):
        return f"<class 'models.BoxFile'> {{'id': '{self.id}', 'name': {self.name}}}"
        

class BoxFolder:
    def __init__(self, id: str, contents: list[BoxFile] = []):
        self.id = id
        self.contents = contents

    def __str__(self):
        return f"<class 'models.BoxFolder'> {{'id': '{self.id}', 'contents': {self.contents}}}"