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

# GCP

## Deploying

1. From GCP CloudShell, connect your GCP account and follow the prompts to login:

    ```bash
    gcloud account login
    ```

2. Now, run the following commands:

    ```bash
    git clone https://github.com/ryananicholson/which-reality --branch i01
    cd which-reality
    gcloud app deploy
    ```

3. If prompted to **Authorize Cloud Shell**, click **AUTHORIZE**.

4. When prompted to continue, type `Y` and `Enter`.

## Tearing Down

1. From GCP CloudShell, run the following command:

    ```bash
    
    ```