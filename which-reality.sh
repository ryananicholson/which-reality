#!/bin/bash

if [[ $1 == "deploy" ]]; then
  read -p "Enter your User ID: " YOUR_USER_ID
  read -sp "Enter a deployment password: " DEPLOY_PASS
  echo -e "\n\033[32m[+] Creating the ${YOUR_USER_ID} deployment user...\033[0m"
  echo -e "    Issuing command: \033[33maz webapp deployment user set --user-name ${YOUR_USER_ID} --password ***REDACTED***\033[0m"
  az webapp deployment user set --user-name ${YOUR_USER_ID} --password "${DEPLOY_PASS}" 1>/dev/null
  if [ $? -ne 0 ]; then 
    echo -e "\033[31m[!] ERROR CREATING USER! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Creating the ${YOUR_USER_ID}-rg resource group...\033[0m"
  echo -e "    Issuing command: \033[33maz group create --name ${YOUR_USER_ID}-rg --location \"Central US\"\033[0m"
  az group create --name ${YOUR_USER_ID}-rg --location "Central US" >/dev/null
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR CREATING RESOURCE GROUP! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Creating the ${YOUR_USER_ID}-plan App service plan...\033[0m"
  echo -e "    Issuing command: \033[33maz appservice plan create --name ${YOUR_USER_ID}-plan --resource-group ${YOUR_USER_ID}-rg --sku B1 --is-linux\033[0m"
  az appservice plan create --name ${YOUR_USER_ID}-plan --resource-group ${YOUR_USER_ID}-rg --sku B1 --is-linux >/dev/null
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR CREATING APP SERVICE PLAN! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Creating the ${YOUR_USER_ID}-app Web App...\033[0m"
  echo -e "    Issuing command: \033[33maz webapp create --resource-group ${YOUR_USER_ID}-rg --plan ${YOUR_USER_ID}-plan --name ${YOUR_USER_ID}-app --runtime \"PHP|7.4\" --deployment-local-git\033[0m"
  az webapp create --resource-group ${YOUR_USER_ID}-rg --plan ${YOUR_USER_ID}-plan --name ${YOUR_USER_ID}-app --runtime "PHP|7.4" --deployment-local-git >/dev/null 2>/dev/null
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR CREATING WEB APP! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Pushing which-reality code...\033[0m"
  if ! [[ $(git remote | grep azure) ]]; then 
    echo -e "    Issuing command: \033[33mgit remote add azure https://${YOUR_USER_ID}@${YOUR_USER_ID}-app.scm.azurewebsites.net/${YOUR_USER_ID}-app.git\033[0m"
    git remote add azure https://${YOUR_USER_ID}@${YOUR_USER_ID}-app.scm.azurewebsites.net/${YOUR_USER_ID}-app.git >/dev/null
    if [ $? -ne 0 ]; then
      echo -e "\033[31m[!] ERROR ADDING REMOTE GIT REPO! Exiting...\033[0m"
      exit 1
    fi
  fi
  echo -e "    Issuing command: \033[33mgit push azure master\033[0m"
  git push azure master >/dev/null 2>/dev/null
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR PUSHING CODE! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Complete! Navigate to https://${YOUR_USER_ID}-app.azurewebsites.net\033[0m"

elif [[ $1 == "teardown" ]]; then
  echo -e "\033[32m[+] Retrieving your deployment user name...\033[0m"
  echo -e "    Issuing command: \033[33maz webapp deployment user show | jq -r .publishingUserName)\033[0m"
  YOUR_USER_ID=$(az webapp deployment user show | jq -r .publishingUserName)
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR RETRIEVING DEPLOYMENT USER NAME! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Removing web app...\033[0m"
  echo -e "    Issuing command: \033[33maz webapp delete --name ${YOUR_USER_ID}-app --resource-group ${YOUR_USER_ID}-rg\033[0m"
  az webapp delete --name ${YOUR_USER_ID}-app --resource-group ${YOUR_USER_ID}-rg >/dev/null
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR DELETING WEB APP! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Removing app service plan...\033[0m"
  echo -e "    Issuing command: \033[33maz appservice plan delete --name ${YOUR_USER_ID}-Plan --resource-group ${YOUR_USER_ID}-rg\033[0m"
  az appservice plan delete --name ${YOUR_USER_ID}-Plan --resource-group ${YOUR_USER_ID}-rg -y >/dev/null
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR DELETING APP SERVICE PLAN! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Removing resource group...\033[0m"
  echo -e "    Issuing command: \033[33maz group delete --name ${YOUR_USER_ID}-rg -y\033[0m"
  az group delete --name ${YOUR_USER_ID}-rg -y >/dev/null
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR DELETING RESOURCE GROUP! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Removing remote git repo...\033[0m"
  echo -e "    Issuing command: \033[33mgit remote remove azure\033[0m"
  git remote remove azure
  if [ $? -ne 0 ]; then
    echo -e "\033[31m[!] ERROR REMOVING REMOTE GIT REPO! Exiting...\033[0m"
    exit 1
  fi
  echo -e "\033[32m[+] Teardown complete!\033[0m"
else
  echo -e "\033[31m[-] You must choose deploy or teardown:\n    $ ./which-reality.sh deploy\n    $ ./which-reality.sh teardown\033[0m"
fi
