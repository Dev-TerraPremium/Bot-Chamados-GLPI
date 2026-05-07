import paramiko

HOST = "192.168.2.110"
PORT = 22
USER = "root"
PASS = "prEm@tErra26"

def main():
    print("Connecting to LXC...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS)

    print("Stopping docker and cleaning daemon.json...")
    ssh.exec_command("systemctl stop docker")
    ssh.exec_command("rm -f /etc/docker/daemon.json")
    
    print("Wiping old /var/lib/docker cache entirely...")
    stdin, stdout, stderr = ssh.exec_command("rm -rf /var/lib/docker")
    stdout.read() # Wait for wipe to complete
    
    print("Starting docker...")
    ssh.exec_command("systemctl start docker")
    
    print("Checking active storage driver...")
    stdin, stdout, stderr = ssh.exec_command("sleep 3 && docker info --format '{{.Driver}}'")
    driver = stdout.read().decode().strip()
    print(f"Active Storage Driver: {driver}")
    
    stdin2, stdout2, stderr2 = ssh.exec_command("df -h")
    print(stdout2.read().decode())
    
    ssh.close()

if __name__ == "__main__":
    main()
