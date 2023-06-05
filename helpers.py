from functools import wraps
from flask import redirect, Flask, session


# define login_required to ensure that pages can't be accessed without login
def login_required(f):
    # here wraps(f) ensures that the name of the function that is passed in is not lost
    # if wraps(f) wasn't used, the docstring of the passed function would have been lost
    @wraps(f)
    # define the function that will wrap around the function passed as argument
    def wrap(*args, **kwargs):
        # if noone is logged in
        if session.get("user_id") is None:
            # redirect to login
            return redirect("/login")
        # otherwise call the function that we are wrapping! (in login_required case, will be loading a page that required login)
        return f(*args, **kwargs)

    # then return wrap function (aka call the wrap function)
    return wrap
