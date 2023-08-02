import os
import shutil
import subprocess
from dotenv import load_dotenv
import streamlit as st

load_dotenv('.env')
root_password = os.getenv('ROOT_PASSWORD')
template_database_username = os.getenv('TEMPLATE_DATABASE_USERNAME')
template_database_password = os.getenv('TEMPLATE_DATABASE_PASSWORD')

st.title('Bulk Delete WordPress')

with st.form(key='del_form'):
    start_number = st.number_input('Start Number', value=36001, step=1)
    end_number = st.number_input('End Number', value=36080, step=1)
    submit_button = st.form_submit_button(label='Ok')
    if submit_button:
        st.toast('Submitted!')
        prgoress_bar = st.progress(0, 'In progress...')

        for i in range(start_number, end_number + 1):
            # 1. 删除数据库
            db_name = "wp_db_" + str(i)
            subprocess.run(["sudo", "mysql", "-u", "root", "-e", "DROP DATABASE " + db_name + ";"])
            
            # 2. 删除WordPress配置文件
            new_dir = "/opt/homebrew/var/www/" + str(i)
            if os.path.exists(new_dir):
                shutil.rmtree(new_dir)

            # 3. 删除Web服务器配置
            server_name = str(i) + ".local"
            config_file = "/opt/homebrew/etc/nginx/servers/" + server_name + ".conf"
            if os.path.exists(config_file):
                os.remove(config_file)
            
            st.toast(f"{i}.local deleted!")
            prgoress_bar.progress((i - start_number + 1) / (end_number - start_number + 1))
    
        # 4. 重启Nginx服务
        subprocess.run(["brew", "services", "restart", "nginx"])
        st.success('All done!')
