1. Conda is preinstalled so we can just create a new environment and activate it 

```
conda create --name corona
conda activate corona
```

2. Install pip 

```
conda install pip
```

3. Clone the github repository and change into directory

```
git clone https://github.com/<org>/<repo>.git
cd .../corona-analysis
```
**Note:** if you get an access denied error, then you first need to create an ssh key and add it to your github account (https://help.github.com/en/enterprise/2.15/user/articles/adding-a-new-ssh-key-to-your-github-account)

4. Install requirements (pip will most likely will fail when installing pyodbc if not done via conda before), 

```
conda install -c conda-forge cartopy
conda install pyodbc
pip install -r requirements.txt
```

It is also recommended to install packages that are not strictly requirementst to run the pipeline, but for debugging and testing:

```
conda install ipython
pip install pytest pytest-xdist
```

5. Install corona package 

```
pip install -e .
```

6. Go to C:\Users\USERNAME\AppData\Roaming and insert the following credentials into file corona.conf:

```
[Database]
host = XXXXX
user = XXXXX
password = XXXXX
database = XXXXX
driver = XXXXX

[Overpass]
endpoint = XXXXXX

[Nominatim]
endpoint = XXXXX
```
**Note:** make sure these credentials are kept secret and not stored in the git repository!

7 (Optional for running test cases): Install pytest via 

```
pip install pytest pytest-xdist
```
