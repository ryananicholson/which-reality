# which-reality

PHP code to determine which reality (Server OS and web app versions) the app is running in (yeah... it's a play on Rick and Morty)

![RickAndMortyImage](https://m.media-amazon.com/images/M/MV5BOGMxMzM4MTEtNzViZS00YTRlLThjOGYtOGEzZWU3MTkxMGM0XkEyXkFqcGdeQXVyNTAyODkwOQ@@._V1_.jpg)

## Azure

### Deploying to Azure Web Apps

1. From Azure CloudShell, run the following (you may see a `urllib3` error... this is expected):

    ```bash
    git clone https://github.com/ryananicholson/which-reality --branch i01
    cd which-reality
    az webapp up --runtime PHP:8.1 --sku B1 --os linux
    ```

1. Acquire URL for web app.

    ```bash
    az webapp list --query [].defaultHostName --output tsv
    ```

### Tearing Down Resource Group

**WARNING!** This assumes you only have this ONE web app. Tear down manually in the Azure Portal if you have other web apps as this may destroy those as well!

1. Acquire the resource group that was automatically created for this web app.

    ```bash
    RESOURCE_GROUP=$(az webapp list --query [].resourceGroup --output tsv)
    ```

1. Delete the resource group.

    ```bash
    az group delete --name $RESOURCE_GROUP
    ```

## GCP

### Deploying to GCP App Engine

1. From GCP CloudShell, connect your GCP account and follow the prompts to login:

    ```bash
    gcloud account login
    ```

1. Now, run the following commands:

    ```bash
    git clone https://github.com/ryananicholson/which-reality --branch i01
    cd which-reality
    gcloud app deploy
    ```

1. If prompted to **Authorize Cloud Shell**, click **AUTHORIZE**.

1. When prompted to continue, type `Y` and `Enter`.

1. When finished, run the following to retrieve your app's URL:

    ```bash
    gcloud app browse
    ```

## Disabling the App

1. Go here and disable the application: https://console.cloud.google.com/appengine/settings