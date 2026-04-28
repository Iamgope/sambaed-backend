from kombu import Queue, Exchange

task_default_queue = "default"
task_default_exchange = "default"
task_default_exchange_type = "topic"
task_default_routing_key = "default.#"
queue_arguments = {"x-queue-type": "quorum"}

task_queues = [
    Queue(task_default_queue, Exchange(task_default_exchange), routing_key=task_default_routing_key, queue_arguments=queue_arguments),
]

task_routes = {

}