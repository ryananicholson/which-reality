# which-reality
PHP code to determine which reality (Server OS and web app versions) the app is running in (yeah... it's a play on Rick and Morty)

![](https://m.media-amazon.com/images/M/MV5BOGMxMzM4MTEtNzViZS00YTRlLThjOGYtOGEzZWU3MTkxMGM0XkEyXkFqcGdeQXVyNTAyODkwOQ@@._V1_.jpg)

## Deploying in Azure

From Azure CloudShell

```bash
git clone https://github.com/ryananicholson/which-reality --branch i01
cd which-reality
az webapp up --runtime PHP:8.1 --sku B1 --logs
```

## Deploying in GCP

From GCP CloudShell

```bash
git clone https://github.com/ryananicholson/which-reality --branch i01
cd which-reality
gcloud app deploy
```
