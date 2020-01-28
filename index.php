<?php 

function command_exist($cmd) {
    $return = shell_exec(sprintf("which %s", escapeshellarg($cmd)));
    return !empty($return);
}

$OS = PHP_OS;

if ($OS == "Darwin") {
    $OS_NAME = "macOS";
    $OS_VER = exec("sw_vers -productVersion");
} elseif (command_exist("lsb_release")) {
    $OS_NAME = exec("lsb_release -a 2>/dev/null | grep Distributor | awk '{print $3}'");
    $OS_VER = exec("lsb_release -a 2>/dev/null | grep Release | awk '{print $2}'");
} elseif (command_exist("rpm")) {
    $OS_NAME = exec("rpm --query redhat-release-server");
    $OS_VER = "";
}

echo "Operating System: " . $OS_NAME . " " . $OS_VER . "<br/>";

if (command_exist("apache2")) {
    $WEBPROG = exec("apache2 -V | grep ^Server\ version");
    if is_null($WEBPROG) {
        echo "Web Server: Apache (Undetermined version)<br/>";
    }
} elseif (command_exist("httpd")) {
    $WEBPROG = exec("httpd -V | grep ^Server\ version");
    if is_null($WEBPROG) {
        echo "Web Server: Apache (Undetermined version)<br/>";
    }
} elseif (command_exist("nginx")) {
    $WEBPROG = exec("nginx -V | grep ^nginx\ version");
    if is_null($WEBPROG) {
        echo "Web Server: NGINX (Undetermined version)<br/>";
    }
}

if !is_null($WEBPROG) {
    echo $WEBPROG . "<br/>";
}

echo "PHP Version: " . phpversion() . "<br/>";

exec("ps -ef", $output);
foreach ($output as $i) {
  echo $i . "<br/>";
}
?>
