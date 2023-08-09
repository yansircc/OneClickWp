start_number = 36001
end_number = 36100

urls = [f"www.{i}.local" for i in range(start_number, end_number + 1)]
output = ",".join(urls)

print(output)