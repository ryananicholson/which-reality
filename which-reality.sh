#!/bin/bash

if [[ $1 == "deploy" ]]; then
  read -p "Enter your User ID: " YOUR_USER_ID
  read -sp "Enter a deployment password: " DEPLOY_PASS
  echo -e "\n\033[32mCreating the ${YOUR_USER_ID} deployment user...\033[0m"
  az webapp deployment user set --user-name ${YOUR_USER_ID} --password ${DEPLOY_PASS} >/dev/null
  echo -e "\033[32mCreating the ${YOUR_USER_ID}-rg resource group...\033[0m"
  az group create --name ${YOUR_USER_ID}-rg --location "Central US" >/dev/null
  echo -e "\033[32mCreating the ${YOUR_USER_ID}-plan App service plan...\033[0m"
  az appservice plan create --name ${YOUR_USER_ID}-plan --resource-group ${YOUR_USER_ID}-rg --sku B1 --is-linux >/dev/null
  echo -e "\033[32mCreating the ${YOUR_USER_ID}-app Web App...\033[0m"
  az webapp create --resource-group ${YOUR_USER_ID}-rg --plan ${YOUR_USER_ID}-plan --name ${YOUR_USER_ID}-app --runtime "PHP|7.3" --deployment-local-git >/dev/null 2>/dev/null
  echo -e "\033[32mPushing which-reality code...\033[0m"
  if [[ $(git remote | grep azure) ]]; then git remote remove azure; fi
  git remote add azure https://${YOUR_USER_ID}@${YOUR_USER_ID}-app.scm.azurewebsites.net/${YOUR_USER_ID}-app.git >/dev/null
  git push azure master >/dev/null 2>/dev/null
  echo -e "\033[32mComplete! Navigate to https://${YOUR_USER_ID}-app.azurewebsites.net\033[0m"

elif [[ $1 == "teardown" ]]; then
  YOUR_USER_ID=$(az webapp deployment user show | jq -r .publishingUserName)
  az webapp delete --name ${YOUR_USER_ID}-app --resource-group ${YOUR_USER_ID}-rg >/dev/null
  az appservice plan delete --name ${YOUR_USER_ID}-Plan --resource-group ${YOUR_USER_ID}-rg -y >/dev/null
  az group delete --name ${YOUR_USER_ID}-rg -y >/dev/null
  git remote remove azure
else
  echo -e "\033[31m[-] You must choose deploy or teardown:\n    $ ./which-reality.sh deploy\n    $ ./which-reality.sh teardown\033[0m"
fi
