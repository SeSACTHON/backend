[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/sesacthon
ansible_python_interpreter=/usr/bin/python3

[masters]
k8s-master ansible_host=${master_public_ip} private_ip=${master_private_ip}

[workers]
k8s-worker-1 ansible_host=${worker_1_public_ip} private_ip=${worker_1_private_ip} workload=application instance_type=t3.medium
k8s-worker-2 ansible_host=${worker_2_public_ip} private_ip=${worker_2_private_ip} workload=async-workers instance_type=t3.medium

[rabbitmq]
k8s-rabbitmq ansible_host=${rabbitmq_public_ip} private_ip=${rabbitmq_private_ip} workload=message-queue instance_type=t3.small

[postgresql]
k8s-postgresql ansible_host=${postgresql_public_ip} private_ip=${postgresql_private_ip} workload=database instance_type=t3.small

[redis]
k8s-redis ansible_host=${redis_public_ip} private_ip=${redis_private_ip} workload=cache instance_type=t3.small

[monitoring]
k8s-monitoring ansible_host=${monitoring_public_ip} private_ip=${monitoring_private_ip} workload=monitoring instance_type=t3.medium

[k8s_cluster:children]
masters
workers
rabbitmq
postgresql
redis
monitoring

