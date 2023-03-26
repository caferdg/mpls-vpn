class Adj:
    def __init__(self, interface="", neighbor=None, ip=""):
        self.ip = ip
        self.interface = interface
        self.neighbor = neighbor

class Router:
    def __init__(self, name="", port=0, id=0, As=None, adjList=None):
        self.name = name
        self.port = port
        self.id = id
        self.As=AS
        self.adjList = adjList

class AS:
    def __init__(self, id=0, name="", routerList=None, prefix="", subList=None):
        self.id = id
        self.name = name
        self.routerList = routerList
        self.prefix = prefix
        list = []
        for i in range(0, 255):
            list.append(Subnet(str(i), False))
        self.subList = list

class Subnet:
    def __init__(self, num="", taken=False):
        self.num = num
        self.taken = False