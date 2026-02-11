from datetime import date

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
    
class SmartsheetContact:
    def __init__(self, email_status:str, email:str, last_day_date: date, **kwargs):
        self.email_status = email_status
        self.email = email
        self.last_day_date = last_day_date

        for k,v in kwargs.items():
            setattr(self,k,v)

    def __str__(self):
        s = "<class 'models.SmartsheetContact'> {"
        s += ", ".join([f"'{k}': {v}" for k,v in vars(self).items()])
        s += "}"
        return s