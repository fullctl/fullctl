class Interface:
    id = "interface"
    name = "Interface"

    def get_price(self, product):
        raise NotImplementedError()
