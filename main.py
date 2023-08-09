import os
import subprocess
from zipfile import ZipFile
from dotenv import load_dotenv
import streamlit as st
import shutil

load_dotenv('.env')
root_password = os.getenv('ROOT_PASSWORD')
template_database_username = os.getenv('TEMPLATE_DATABASE_USERNAME')
template_database_password = os.getenv('TEMPLATE_DATABASE_PASSWORD')

template_zip_default = os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'blueprint.zip')
blueprint_db_file_default = os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'blueprint_db.sql')
wp_config_template_path = os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'blueprint_wp-config.php')

st.set_page_config(page_title='Bulk Build WordPress', page_icon='🐳', layout='centered')
st.title('Bulk Build WordPress')

with st.form(key='my_form'):
    blueprint_zip_uploaded = st.file_uploader('Upload blueprint.zip', type='zip')
    start_number = st.number_input('Start Number', value=36001, step=1)
    end_number = st.number_input('End Number', value=36080, step=1)
    submit_button = st.form_submit_button(label='Ok')
    if submit_button:
        st.toast('表格提交成功!')
        progress_bar = st.progress(0, 'In progress...')
        
        # Default paths
        template_zip = template_zip_default
        blueprint_db_file = blueprint_db_file_default
        
        # Check if user uploaded a blueprint.zip file
        if blueprint_zip_uploaded is not None:
            blueprint_zip_path = os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'temp.zip')
            with open(blueprint_zip_path, 'wb') as f:
                f.write(blueprint_zip_uploaded.getbuffer())
            
            # Extract the uploaded zip
            with ZipFile(blueprint_zip_path, 'r') as zip_ref:
                zip_ref.extractall(os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'temp'))
            
            # Detect the first-level-folder
            first_level_folder = os.listdir(os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'temp'))[0]
            base_path = os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'temp', first_level_folder)
            
            # Replace the wp-config.php with your template
            shutil.copy(wp_config_template_path, os.path.join(base_path, "app", "public", "wp-config.php"))
            
            # Zip the directory
            zipped_template_path = os.path.join(base_path, "app", "public_zip.zip")
            with ZipFile(zipped_template_path, 'w') as zipf:
                for root, _, files in os.walk(os.path.join(base_path, "app", "public")):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, os.path.join(base_path, "app", "public"))
                        zipf.write(file_path, arcname=arcname)

            # Update the paths to use the uploaded files
            template_zip = zipped_template_path
            blueprint_db_file = next(os.path.join(base_path, "app", "sql", f) for f in os.listdir(os.path.join(base_path, "app", "sql")) if f.endswith('.sql'))

        nginx_notice_string = f'# custom domains from {start_number} to {end_number}\n'
        localhost_notice_string = f'# custom domains from {start_number} to {end_number}\n'

        for i in range(start_number, end_number + 1):
            # 0. 检查用户是否存在
            query = f"SELECT EXISTS(SELECT 1 FROM mysql.user WHERE user = '{template_database_username}');"
            check_user = subprocess.run(["sudo", "mysql", "-u", "root", "-p" + root_password, "-e", query], capture_output=True, text=True)
            
            # 创建数据库
            db_name = "wp_db_" + str(i)
            subprocess.run(["sudo", "mysql", "-u", "root", "-p" + root_password,
                        "-e", "CREATE DATABASE " + db_name + ";"])
            
            if '0' in check_user.stdout:  # 如果用户不存在
                # 创建用户
                subprocess.run(["sudo", "mysql", "-u", "root", "-p" + root_password, "-e",
                            f"CREATE USER '{template_database_username}'@'localhost' IDENTIFIED BY '{template_database_password}';"])

            # 授权用户
            subprocess.run(["sudo", "mysql", "-u", "root", "-p" + root_password, "-e",
                    f"GRANT ALL PRIVILEGES ON {db_name}.* TO '{template_database_username}'@'localhost';"])

            # 使用blueprint_db文件填充新创建的数据库
            subprocess.run(
                f"sudo mysql -u {template_database_username} -p{template_database_password} {db_name} < {blueprint_db_file}", shell=True)

            # 2. 创建WordPress配置文件
            new_dir = os.getenv('BASE_DIR') + str(i)

            # 解压WordPress模板文件
            with ZipFile(template_zip, 'r') as zip_ref:
                zip_ref.extractall(new_dir)

            with open(new_dir + "/wp-config.php", "r") as f:
                config = f.read()
            config = config.replace("database_name_here", db_name)
            config = config.replace(
                "username_here", template_database_username)  # 替换数据库用户名
            config = config.replace(
                "password_here", template_database_password)  # 替换数据库密码
            config = config.replace("example.local", str(i) + ".local")
            with open(new_dir + "/wp-config.php", "w") as f:
                f.write(config)

            # 3. 创建Web服务器配置
            server_name = str(i) + ".local"
            # Use string as nginx template
            config = f'''server {{
                listen 80;
                server_name {server_name} www.{server_name};

                root {os.getenv('BASE_DIR')}{i};
                index index.php;

                location / {{
                    try_files $uri $uri/ /index.php$is_args$args;
                }}

                location ~ \.php$ {{
                    fastcgi_pass   127.0.0.1:9000;
                    fastcgi_index  index.php;
                    fastcgi_param  SCRIPT_FILENAME $document_root$fastcgi_script_name;
                    include        fastcgi_params;
                }}
            }}'''
            with open(os.getenv("NGINX_SERVERS_DIR") + server_name + ".conf", "w") as f:
                f.write(config)
            st.toast(f"{i}.local 创建成功!")
            progress_bar.progress((i - start_number + 1) / (end_number - start_number + 1))
            nginx_notice_string += f"address /www.{i}.local/192.168.1.3\n"
            localhost_notice_string += f"192.168.1.3    www.{i}.local\n"

        # print nginx notice info to user
        st.write('将以下添加到软路由的"服务"->"smartDNS"->"Domain Rules"->"域名地址"中末尾')
        st.code(nginx_notice_string)
        # st.code(localhost_notice_string)
        # 4. 重启Nginx服务
        subprocess.run(["brew", "services", "restart", "nginx"])
        st.code('''
                # 重启软路由DNS服务
                /etc/init.d/dnsmasq restart
                /etc/init.d/smartdns restart
                /etc/init.d/passwall restart
                # 清除DNS缓存
                sudo dscacheutil -flushcache
                sudo killall -HUP mDNSResponder
                ''')
        shutil.rmtree(os.path.join(os.getenv('BASE_DIR'), 'blueprint', 'temp'))
        st.toast('全部完成!')