How to run tests
================

Installation
------------
```
pip install pytest pytest-xdist
```

Use cases
---------

Run all unit tests:
```
py.test -s -k unit .
```

Run all tests that generate html reports:
```
py.test -s -k reports .
```

Other common use cases
----------------------

Run all tests in parallel with 10 processes with:
```
py.test -x -n 10 -v .
```

Run a specific test and show the standout output:
```
py.test -s -k dce88ade729511ea80ea42a51fad92d3
```
