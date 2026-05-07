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

    print("Clearing all Redis locks and blocks (FLUSHALL)...")
    stdin, stdout, stderr = ssh.exec_command('docker exec bot-chamados-redis redis-cli FLUSHALL')
    print("Redis Output:", stdout.read().decode().strip())
    
    ssh.close()

if __name__ == "__main__":
    main()
