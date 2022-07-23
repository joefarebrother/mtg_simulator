def copy_excluding(x, attrs):
    """Creates a shallow copy of x that excludes the given attributes"""
    y = object.__new__(x.__class__)
    for k, v in x.__dict__.items():
        if v not in attrs:
            y.__dict__[k] = v
    return y
