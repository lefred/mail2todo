# Mail 2 Todo

This small Python 3 script, is used to create new todo tasks in [myTinyTodo](https://www.mytinytodo.net/)
from an email.

## Requirements

- myTinyTodo >= 1.6.10
- Python 3.8 >=
- MySQL Connector Python
- MySQL 8.0 with X Protocol
- Imap over SSL 

## How does it work ?

When the script is configured and running, you can send (or forward) to a dedicated email account.

Every 2 minutes, the script will check for email and create a task for each new email.

The email's Subject will be the title of the task and the first line will be parsed to find the
list and tags.

List and tags should be on the first line and prefixed with '@'. The first word totally in uppercase
will be considered as the list's name.

Example:

```
  @MYSQL @reply @urgent
```

The line above means that the task is for the "MYSQL" list and the tags will be "reply" and "urgent".

## Systemd

There is a script you can edit to start and stop the process using systemd.

This is how to use it:

```
  sudo cp mail2todo.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl start mail2todo
  sudo systemctl status mail2todo
```

By default DEBUG mode is enabled, you can see the output using journald:

```
  sudo journactl -u mail2todo -f
```

## Examples

![Selection_063](https://user-images.githubusercontent.com/609675/179944345-49c9ae53-216a-4c31-a49a-97b27c9eb3bd.png)

![Selection_064](https://user-images.githubusercontent.com/609675/179944412-8c07c13f-fc1f-4940-b188-9ebe6cb194d5.png)

![Selection_065](https://user-images.githubusercontent.com/609675/179944484-ff0acffb-ce48-4b36-b2da-c9a0d316cbae.png)

