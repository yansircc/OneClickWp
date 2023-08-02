from locust import HttpUser, task, between

class WordPressUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def load_wordpress_sites(self):
        for i in range(36001, 36081):  # assuming you have your WordPress sites numbered 1 to 80
            self.client.get(f"http://www.{i}.local/")
            
