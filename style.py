green1 = '97ba66'
green2 = 'A7D489'

pallet1 = ['#283044', '#78a1bb', '#ebf5ee', '#bfa89e', '#bfa89e']

def headline1():
    return """
    font: bold;
    font-size: 24px;
    color: #283044
    """

def headline2():
    return """
    font: bold;
    font-size: 16px;
    color: #8b786d
    """

def headline3():
    return """
    font: bold;
    font-size: 14px;
    color: black
    """


def grey1():
    return """
    background-color: lightgrey;
    """


def body1():
    return """
    font: bold;
    """

def body2():
    return """
    color: black
    """

def box1():
    return """
        QGroupBox {
        background-color:#ebf5ee;
        font:16pt Arial;
        font-weight: bold;
        color:#283044;
        border:2px solid;
        border-radius:10px;
        border-color: #283044;
        margin: 5px;
        }
        QGroupBox::title {
            left: 10px;
            top: 4px;
        }
        
    """

def box2():
    return """
        QGroupBox {
        background-color:#78a1bb;
        font:16pt Arial;
        font-weight: bold;
        color:white;
        border:2px solid gray;
        border-radius:10px;
        border-color: #283044;
        margin: 5px;
        }
        QGroupBox::title {
            left: 10px;
            top: 4px;
        }
    """


def box3():
    return """
        QGroupBox {
        background-color:#ebf5ee;
        font:16pt Arial;
        font-weight: bold;
        color:#8b786d;
        border:2px solid;
        border-radius:10px;
        border-color: #8b786d;
        margin: 10px;
        }
    """

def box4():
    return """
        QGroupBox {
        background-color:#bfa89e;
        font:16pt Arial;
        font-weight: bold;
        color:white;
        border:2px solid gray;
        border-radius:10px;
        border-color: #8b786d;
        }
    """


def box5():
    return """
        QGroupBox {
        background-color:#E5E4E2;
        border:2px;
        border-radius:5px;
        }
    """

def box6():
    return """
        QGroupBox {
        border:0px solid gray;
        border-radius:1px;
        }
    """

