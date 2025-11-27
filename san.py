# example.py
import os, sys, math

def my_function(  x, y ):  # Extra spaces around parameters (E211)
    print(    "Hello, World!" )  # Extra spaces inside parentheses (E201)
    if x>y:  # Missing spaces around operator (E225)
        print(f"{x} is greater than {y}")
    else:print(f"{x} is less than or equal to {y}")  # Statement on the same line as else (E701)

my_function( 5, 3 )

