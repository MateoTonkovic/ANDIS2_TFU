
import os
import json
import logging
import pika
from typing import Callable, Any
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


class MessageQueue:
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
    
    def _connect(self):
        """Establecer conexión a RabbitMQ"""
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            
            # Declarar cola con durabilidad
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                arguments={
                    'x-max-length': 10000,  
                    'x-message-ttl': 3600000 
                }
            )
            logger.info(f"Conectado a cola RabbitMQ: {self.queue_name}")
        except Exception as e:
            logger.warning(f"Falló conexión a RabbitMQ (reintentará después): {e}")
    
    def publish(self, message: dict) -> bool:
        try:
            if not self.connection or self.connection.is_closed:
                self._connect()
            if not self.channel or self.channel.is_closed:
                self._connect()
            
            self.channel.basic_publish(
                exchange='',
                routing_key=self.queue_name,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  
                    content_type='application/json'
                )
            )
            logger.info(f"Mensaje publicado a {self.queue_name}: {message.get('type', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Falló al publicar mensaje: {e}")
            return False
    
    def consume(self, callback: Callable[[dict], None], auto_ack: bool = False):
        try:
            if not self.channel or self.channel.is_closed:
                self._connect()
            
            def wrapper(ch, method, properties, body):
                try:
                    message = json.loads(body)
                    logger.info(f"Procesando mensaje: {message.get('type', 'unknown')}")
                    callback(message)
                    
                    if not auto_ack:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    logger.error(f"Error procesando mensaje: {e}")
                    if not auto_ack:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            self.channel.basic_qos(prefetch_count=1)
            
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=wrapper,
                auto_ack=auto_ack
            )
            
            logger.info(f"Comenzó a consumir desde {self.queue_name}")
            self.channel.start_consuming()
        except Exception as e:
            logger.error(f"Error consumiendo mensajes: {e}")
            raise
    
    def get_queue_size(self) -> int:
        try:
            if not self.channel or self.channel.is_closed:
                self._connect()
            
            method = self.channel.queue_declare(
                queue=self.queue_name,
                durable=True,
                passive=True  
            )
            return method.method.message_count
        except Exception as e:
            logger.error(f"Error obteniendo tamaño de cola: {e}")
            return -1
    
    def close(self):
        """Cerrar la conexión"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logger.info(f"Conexión cerrada a {self.queue_name}")
        except Exception as e:
            logger.error(f"Error cerrando conexión: {e}")


class AsyncTaskProcessor:
    def __init__(self, queue_name: str):
        self.queue = MessageQueue(queue_name)
        self.handlers = {}
        self.worker_thread = None
        self.running = False
    
    def register_handler(self, task_type: str, handler: Callable):
        """Registrar un handler para un tipo de tarea específico"""
        self.handlers[task_type] = handler
        logger.info(f"Handler registrado para tipo de tarea: {task_type}")
    
    def enqueue_task(self, task_type: str, data: dict) -> bool:
        message = {
            "type": task_type,
            "data": data,
            "timestamp": str(os.times())
        }
        return self.queue.publish(message)
    
    def _process_message(self, message: dict):
        task_type = message.get("type")
        data = message.get("data", {})
        
        handler = self.handlers.get(task_type)
        if handler:
            try:
                handler(data)
                logger.info(f"Tarea procesada exitosamente: {task_type}")
            except Exception as e:
                logger.error(f"Error en handler para {task_type}: {e}")
                raise
        else:
            logger.warning(f"No hay handler registrado para tipo de tarea: {task_type}")
    
    def start_worker(self):
        if self.running:
            logger.warning("Worker ya está corriendo")
            return
        
        self.running = True
        
        def worker():
            logger.info("Iniciando queue worker")
            try:
                self.queue.consume(self._process_message)
            except KeyboardInterrupt:
                logger.info("Worker interrumpido")
                self.running = False
        
        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
        logger.info("Queue worker iniciado en background")
    
    def stop_worker(self):
        self.running = False
        self.queue.close()
        logger.info("Queue worker detenido")


def check_rabbitmq_health() -> dict:
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(params)
        connection.close()
        return {"status": "healthy", "service": "rabbitmq"}
    except Exception as e:
        return {"status": "unhealthy", "service": "rabbitmq", "error": str(e)}
