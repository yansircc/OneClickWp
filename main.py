import os
import subprocess
import zipfile
from dotenv import load_dotenv
import streamlit as st
# import random

load_dotenv('.env')
root_password = os.getenv('ROOT_PASSWORD')
template_database_username = os.getenv('TEMPLATE_DATABASE_USERNAME')
template_database_password = os.getenv('TEMPLATE_DATABASE_PASSWORD')

template_zip = "/opt/homebrew/var/www/blueprint/blueprint.zip"
nginx_config_template = "/opt/homebrew/var/www/blueprint/blueprint_nginx.conf"
blueprint_db_file = "/opt/homebrew/var/www/blueprint/blueprint_db.sql"

st.set_page_config(page_title='Bulk Build WordPress', page_icon='🐳', layout='centered')
st.title('Bulk Build WordPress')

with st.form(key='my_form'):
    start_number = st.number_input('Start Number', value=36001, step=1)
    end_number = st.number_input('End Number', value=36080, step=1)
    submit_button = st.form_submit_button(label='Ok')
    if submit_button:
        st.toast('表格提交成功!')
        prgoress_bar = st.progress(0, 'In progress...')

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
            new_dir = "/opt/homebrew/var/www/" + str(i)

            # 解压WordPress模板文件
            with zipfile.ZipFile(template_zip, 'r') as zip_ref:
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
            with open(nginx_config_template) as f:
                config = f.read()
            config = config.replace("example.local", server_name)
            config = config.replace("/opt/homebrew/var/www/example", new_dir)
            config = config.replace("example", str(i))
            with open("/opt/homebrew/etc/nginx/servers/" + server_name + ".conf", "w") as f:
                f.write(config)
            st.toast(f"{i}.local 创建成功!")
            prgoress_bar.progress((i - start_number + 1) / (end_number - start_number + 1))
            nginx_notice_string += f"address /www.{i}.local/192.168.1.3\n"
            localhost_notice_string += f"192.168.1.3    www.{i}.local\n"

        # print nginx notice info to user
        st.write('将以下添加到软路由的"服务"->"smartDNS"->"Domain Rules"->"域名地址"中末尾')
        st.code(nginx_notice_string)
        # st.code(localhost_notice_string)
        # 4. 重启Nginx服务
        subprocess.run(["brew", "services", "restart", "nginx"])
        st.toast('全部完成!')
        # random_site_url = str(random.randint(start_number, end_number)) + ".local"
        # st.success(f"建议访问这个随机域名来做验证: http://www.{random_site_url}")
        st.code('''
                # 重启软路由DNS服务
                /etc/init.d/dnsmasq restart
                /etc/init.d/smartdns restart
                /etc/init.d/passwall restart
                # 清除DNS缓存
                sudo dscacheutil -flushcache
                sudo killall -HUP mDNSResponder
                ''')