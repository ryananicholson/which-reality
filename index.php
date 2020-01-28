<html>
<head>
  <title>Oh geez... What reality am I in?</title>
</head>

<body>
<h1> Server Information</h1>
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
    if ($WEBPROG == "") {
        $WEBPROG = "Web Server: Apache (Undetermined version)";
    }
} elseif (command_exist("httpd")) {
    $WEBPROG = exec("httpd -V | grep ^Server\ version");
    if ($WEBPROG == "") {
        $WEBPROG = "Web Server: Apache (Undetermined version)";
    }
} elseif (command_exist("nginx")) {
    $WEBPROG = exec("nginx -V | grep ^nginx\ version");
    if ($WEBPROG == "") {
        $WEBPROG = "Web Server: NGINX (Undetermined version)";
    }
}

echo $WEBPROG . "<br/>";

echo "PHP Version: " . phpversion() . "<br/>";
?>

<h1> Running Processes </h1>
<?php
exec("ps -ef", $output);
foreach($output as $i) {
    echo $i . "<br/>";
}
?>
</body>
</html>
