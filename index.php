<html>
<head>
  <link rel="stylesheet" href="style.css">
  <title>Oh geez... What reality am I in?</title>
</head>

<!-- TODO: Remember to upgrade Azure subscription before trial ends. Company credit card is 4123-4567-8910-1112. -->
  
<body>
<img src="Cloud_Ace_Final.png" width="250px" style="display:block;margin-left:auto;margin-right:auto;" />
<h1> Server Information</h1>
<?php 

function command_exist($cmd) {
    $return = shell_exec(sprintf("which %s", escapeshellarg($cmd)));
    return !empty($return);
}

if (command_exist("uname")) {
    $OS_NAME = exec("uname -r");
    $OS_VER = "";
}

echo "Kernel version: " . $OS_NAME . " " . $OS_VER . "<br/>";

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
    $WEBPROG = exec("nginx -V  2>&1 | grep ^nginx\ version | sed 's/^nginx/Server/'");
    if ($WEBPROG == "") {
        $WEBPROG = "Web Server: NGINX (Undetermined version)";
    }
}

echo $WEBPROG . "<br/>";

echo "PHP Version: " . phpversion() . "<br/>";
?>

<h1> Running Processes </h1>

<div id=terminal>
<?php
exec("ps -ef", $output);
foreach($output as $i) {
    echo "<code>" . $i . "</code><br/>";
}
?>
</div>
</body>
</html>
