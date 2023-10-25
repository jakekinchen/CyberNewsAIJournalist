import subprocess

php_script = "/Users/jakekinchen/Builds/python_scraping_test/test.php"
result = subprocess.check_output(["php", php_script])
print(result.decode("utf-8"))