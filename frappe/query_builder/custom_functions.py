from pypika import functions as fn



class GROUP_CONCAT(fn.DistinctOptionFunction):
    def __init__(self, col, alias=None):
        super(GROUP_CONCAT, self).__init__("GROUP_CONCAT", col, alias=alias)


class STRING_AGG(fn.DistinctOptionFunction):
    def __init__(self, col, val=",", alias=None):
        super(STRING_AGG, self).__init__("STRING_AGG", col, val, alias=alias)
