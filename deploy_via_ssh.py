import os
import sys
import time
import paramiko

HOST = "192.168.2.110"
PORT = 22
USER = "root"
PASS = "prEm@tErra26"

LOCAL_TAR = r"c:\projects\Bot-Chamados-GLPI\bot.tar.gz"
LOCAL_DEPLOY_SH = r"c:\projects\Bot-Chamados-GLPI\remote-deploy.sh"
LOCAL_ENV_DOCKER = r"c:\projects\Bot-Chamados-GLPI\.env.docker"

def safe_print(text):
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        sys.stdout.write(text.encode(enc, errors="replace").decode(enc))
        sys.stdout.flush()

def main():
    print(f"Connecting to SSH {USER}@{HOST}:{PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
        print("Connected successfully!")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    # 1. SFTP transfer
    print("Opening SFTP session...")
    sftp = ssh.open_sftp()
    
    remote_dir = "/opt/bot-chamados-glpi"
    print(f"Ensuring remote directory {remote_dir} exists...")
    try:
        sftp.mkdir(remote_dir)
        print(f"Created {remote_dir}")
    except IOError:
        print(f"Directory {remote_dir} already exists.")

    print(f"Uploading {LOCAL_TAR} -> {remote_dir}/bot.tar.gz...")
    sftp.put(LOCAL_TAR, f"{remote_dir}/bot.tar.gz")

    print(f"Uploading {LOCAL_ENV_DOCKER} -> {remote_dir}/.env.docker...")
    sftp.put(LOCAL_ENV_DOCKER, f"{remote_dir}/.env.docker")
    
    print(f"Uploading {LOCAL_DEPLOY_SH} -> /tmp/remote-deploy.sh...")
    sftp.put(LOCAL_DEPLOY_SH, "/tmp/remote-deploy.sh")
    
    sftp.close()
    print("Files uploaded successfully.")

    # 2. Extract tarball remotely
    print("Extracting workspace tarball remotely...")
    stdin, stdout, stderr = ssh.exec_command(f"tar -xzf {remote_dir}/bot.tar.gz -C {remote_dir}", get_pty=True)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print(f"Failed to extract tarball. Error: {stderr.read().decode()}")
        sys.exit(1)
    print("Workspace extracted successfully.")

    # 3. Make script executable and run it
    print("Executing remote-deploy.sh remotely...")
    stdin, stdout, stderr = ssh.exec_command("chmod +x /tmp/remote-deploy.sh && /tmp/remote-deploy.sh", get_pty=True)
    
    # Read output in real-time
    while True:
        line = stdout.readline()
        if not line:
            break
        safe_print(line)

    exit_status = stdout.channel.recv_exit_status()
    print(f"\nDeployment script exited with status: {exit_status}")

    if exit_status == 0:
        print("\nDeploy was successful! Let's fetch the WhatsApp QR code logs...")
        print("Waiting 15 seconds for whatsapp service to initialize...")
        time.sleep(15)
        
        print("Streaming WhatsApp logs to find QR code (press Ctrl+C to stop)...")
        stdin, stdout, stderr = ssh.exec_command(f"docker compose -f {remote_dir}/compose.yml logs -f whatsapp", get_pty=True)
        
        # Read logs for 3 minutes or until QR code or pairing is successful
        start_time = time.time()
        while time.time() - start_time < 180:
            if stdout.channel.recv_ready():
                line = stdout.readline()
                if not line:
                    break
                safe_print(line)
            else:
                time.sleep(0.5)

    ssh.close()

if __name__ == "__main__":
    main()
