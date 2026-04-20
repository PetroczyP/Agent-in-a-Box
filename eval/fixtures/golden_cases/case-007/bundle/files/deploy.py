import os
import sys


def deploy_to_host(hostname, package_path):
    """Deploy a package to a remote host via scp."""
    cmd = f"scp {package_path} deploy@{hostname}:/opt/releases/"
    os.system(cmd)
    os.system(f"ssh deploy@{hostname} 'systemctl restart app'")
    print(f"Deployed to {hostname}")


if __name__ == "__main__":
    host = sys.argv[1]
    pkg = sys.argv[2]
    deploy_to_host(host, pkg)
