# gitea-archiver

A simple python script to download archives of all of a user's repositories from [Gitea[(https://gitea.io)

# Usage

```
usage: gitea-archiver.py [-h] --url URL --token TOKEN --dest DEST
                         [--break-locks]

Downloads archives of all gitea repositories for a user.

optional arguments:
  -h, --help     show this help message and exit
  --url URL      Gitea instance URL
  --token TOKEN  Gitea access token
  --dest DEST    Archive destination
  --break-locks  Break cache lock
  ```
