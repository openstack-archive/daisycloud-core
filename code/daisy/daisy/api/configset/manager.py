from daisy.api.configset.clush import config_clushshell

class configBackend():
    def __init__(self, type, req, role_id):
        self.type = type
        self._instance = None
        
        if type == "clushshell":
            self._instance = config_clushshell(req, role_id)
        elif type == "puppet":
            pass
            
    def push_config(self):
        self._instance.push_config()
        
    