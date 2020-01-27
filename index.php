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
    $WEBPROG = exec("apache2 -V | grep ^Server\ version")
} elseif (command_exist("httpd")) {
    $WEBPROG = exec("httpd -V | grep ^Server\ version")
}

echo $WEBPROG;

echo "Web Server: " . $_SERVER['SERVER_SIGNATURE'] . "<br/>";
echo "PHP Version: " . phpversion() . "<br/>";
echo phpinfo();
?>
