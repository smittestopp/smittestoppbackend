1. After logging into the linux VM, install conda

```
wget https://repo.anaconda.com/archive/Anaconda3-2020.02-Linux-x86_64.sh
sh Anaconda3-2020.02-Linux-x86_64.sh
```

2. (Optional) Create a new environment and activate it 

```
conda create --name corona
conda activate corona
```

3. Install pip 

```
conda install pip
```

4. Clone the github repository and change into directory

```
git clone https://github.com/<org>/<repo>.git
cd .../corona-analysis
```
**Note:** if you get an access denied error, then you first need to create an ssh key and add it to your github account (https://help.github.com/en/enterprise/2.15/user/articles/adding-a-new-ssh-key-to-your-github-account)

5. Install requirements (pip will most likely will fail when installing pyodbc if not done via conda before), 

```
conda install -c conda-forge cartopy
conda install pyodbc
pip install -r requirements.txt
```

6. Install corona package 

```
pip install -e .
```

7. Create and open corona config file

```
mkdir ~/.config
vim ~/.config/corona.conf
```

8. Insert config at the top of file

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
