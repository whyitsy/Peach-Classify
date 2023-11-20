# 导入库
import paho.mqtt.client as ph_mqtt_clt
import json
import threading
import base64
import requests
import time
from enum import Enum

class Mqtt_Clt():
    """
    用于表征Mqtt客户端的类
    """
    def __init__(self, ip_broker, port_broker, topic_sub, topic_pub, time_out_secs):
        """
        parameters:ip_broker:broker的IP地址
                   port_broker:连接服务的端口
                   topic_sub:订阅话题
                   topic_pub:发布话题
                   time_out_secs:连接超时的时间
        """
        self.mqtt_clt = ph_mqtt_clt.Client()    # 构造Mqtt客户端
        # self.mqtt_clt.on_connect = self.on_connect
        # self.mqtt_clt.on_connect_fail = self.on_connect_fail
        self.mqtt_clt.on_message = self.on_message  # 设置Mqtt客户端回调on_message为本类成员方法on_message
        self.topic_sub = topic_sub  # 设置订阅话题
        self.topic_pub = topic_pub  # 设置发布话题
        self.msg = {}   # 初始化接收消息的字典类成员变量msg为空({})
        self.mqtt_clt.connect(ip_broker, port_broker, time_out_secs)    # 连接Mqtt Broker
        self.mqtt_clt.subscribe(self.topic_sub, qos=0)  # 订阅相关话题
        self.mqtt_clt.loop_start()  # 开启接收循环

    # def on_connect(self, client, userdata, flags, rc):
    #     if rc == 0:
    #         print("Mqtt连接成功!")
    #         self.mqtt_clt.subscribe(self.topic_sub, qos=0)
    #         self.mqtt_clt.loop_forever()
    #     else:
    #         print("Mqtt连接失败!")
    #         os._exit(0)

    # def on_connect_fail(self, client, userdata):
    #     print("Mqtt连接出现问题!")
    #     os._exit(0)

    def __del__(self):
        self.mqtt_clt.loop_forever()    # 结束接收循环
        self.mqtt_clt.disconnect()  # 断开连接


    def on_message(self, client, userdata, message):
        """
        parameters:client:回调返回的客户端实例
                   userdata:Client()或user_data_set()中设置的私有用户数据
                   msg:MQTTMessage实例,包含topic,payload,qos,retain
        functions:接收消息的回调,提取消息中的相关内容
        """
        self.msg = json.loads(message.payload.decode())
        # print("%%%%%%%%%%%%")
        # print("msg_json:", self.msg)

    def send_json_msg(self, msg):
        """
        parameters:msg:json消息
        returns:无
        functions:在指定的话题上发布消息
        """
        self.mqtt_clt.publish(self.topic_pub, payload="{}".format(msg))

    def control_device(self, str_key, str_value):
        """
        parameters:str_key:键的字符串
                   str_value:值的字符串
        functions:控制设备
        """
        self.send_json_msg(json.dumps({str_key: str_value}))

class PosObj(Enum):
    """
    物体的位置
    """
    before_1st = 0  # 在1号对管之前
    at_1st = 1  # 在1号对管处
    between_1st_and_2nd = 2 # 在1,2号对管之间
    at_2nd = 3  # 在2号对管处
    between_2nd_and_3rd = 4 # 在2,3号对管之间
    at_3rd = 5  # 在3号对管处
    beyond_3rd = 6  # 在3号对管之后

class StateRod(Enum):
    """
    推杆状态
    """
    stop = 0    # 停止
    push = 1    # 推出
    pull = 2    # 拉回

class FS_IIOTA():
    """
    表征智能分拣系统行为的类
    """
    # def __init__(self, ip_mqtt_broker, website_back_end, total_tolerance=100):
    def __init__(self, ip_mqtt_broker, website_back_end):
        """
        parameters:ip_mqtt_broker:Mqtt broker的IP地址
                   website_back_end:用于识别的服务端(后端)网址
        """
        self.mqtt_clt = Mqtt_Clt(ip_mqtt_broker, 1883, "bb", "aa",
                                 50)    # 构造Mqtt客户端
        self.website_back_end = website_back_end    # 获取用于识别的后端网址
        self.obj_pos = PosObj.before_1st    # 认为当前物体所在位置为1号对管之前
        self.stat_stack_rod = StateRod.stop # 认为当前上货杆(1号推杆)停止
        self.stat_classify_rod = StateRod.stop  # 认为当前分类杆(2/3/4号推杆停止)
        self.classify_rod_act_num = 1   # 表征哪个分类杆要动作(1:无效,2/3/4:2/3/4号分类杆动作)
        self.classify_rod_act_num_temp = self.classify_rod_act_num  # 上述变量的"替身"变量
        # self.mqtt_clt.control_device("control_device", "enable")
        # time.sleep(1)
        # self.mqtt_clt.control_device("conveyor", "stop")
        # time.sleep(1)
        # self.mqtt_clt.control_device("rod_control", "all_pull")
        # time.sleep(3)
        self.mqtt_clt.control_device("conveyor", "run") # 控制传送带运行
        ####################################################
        time.sleep(3) # 6s
        ####################################################
        self.timer_stack_rod = threading.Timer(1.5, self.handle_timer_statck_rod)   # 定义一个3.5秒的用于控制上货杆再次动作的定时器
        self.timer_classify_rod = None  # 初始化分类杆再次动作的定时器
        
        # 先发送消息将货推出再将上货杆设置为推出状态
        self.mqtt_clt.control_device("rod_control", "first_push")   # 控制上货杆推出
        self.stat_stack_rod = StateRod.push # 将上货杆的状态设为推出
        # self.t_handle_mqtt_json_msg = threading.Thread(target=self.handle_mqtt_json_msg, kwargs={"total_tolerance":
        #                                                                                              total_tolerance})
        # self.t_handle_mqtt_json_msg.start()
        self.timer_stack_rod.start()    # 启动上货杆再次动作的定时器

    def __del__(self):
        self.mqtt_clt.control_device("rod_control", "all_pull") # 控制所有推杆拉回
        time.sleep(3)
        self.mqtt_clt.control_device("conveyor", "stop")    # 控制传送带停止
        time.sleep(1)
        # print("FS_IIOTA_del")

    def handle_mqtt_json_msg(self, total_tolerance):
        """
        functions:以循环的方式对Mqtt客户端的有效消息进行处理,在发生异常的时候记录异常总次数;并触发相应的状态机
        """
        cnt_except = 0  # 定义发生异常的计数量(初始化为0)
        while cnt_except < total_tolerance: # 在发生异常的计数量小于容忍值时一直循环
            if self.mqtt_clt.msg != {}: # 在mqtt接收到的消息非空时
                if "image" in self.mqtt_clt.msg:    # 如果接收到的是图像的话
                    img_data = base64.b64decode(self.mqtt_clt.msg["image"]) # 解码获得图像数据
                    try:
                        result = json.loads(requests.post(self.website_back_end, data=img_data).text)   # 将图像数据img_data给POST出去并获得相应的结果result
                        print("识别结果:", result)
                        try:
                            assert len(result["results"]) == 1  # 确保识别结果result中的键"results"中的值只有1个
                            label = result["results"][0]["label"]   # 获得识别结果中的label
                            if label == "ripe": # 如果label是"ripe",则2号推杆将运动
                                self.classify_rod_act_num = 2
                                print("ripe:2号推杆将动作")
                            elif label == "half_ripe":  # 如果label是"half-ripe",则3号推杆将运动
                                self.classify_rod_act_num = 3
                                print("half_ripe:3号推杆将动作")
                            elif label == "raw":    # 如果label是"raw",则4号推杆将运动
                                self.classify_rod_act_num = 4
                                print("raw:4号推杆将动作")
                            else:   # 否则,哪个推杆都不动
                                self.classify_rod_act_num = 1
                                print("哪个分类杆都不动作")
                        except: # 获得结果时发生异常,则cnt_except自加1
                            print("未获得有效结果!")
                            cnt_except += 1
                    except: # post时发生异常,则cnt_except自加1
                        print("无法post!")
                        cnt_except += 1
                elif "first_switch" in self.mqtt_clt.msg: # 如果接收到的是1号对管的消息 判断是进还是出
                    if self.obj_pos == PosObj.before_1st and self.mqtt_clt.msg["first_switch"]: # 如果物体当前位置在1号对管之前,并且当前收到的mqtt消息为1号对管有遮挡时,将物体当前位置改为处于1号对管处
                        self.obj_pos = PosObj.at_1st
                    elif self.obj_pos == PosObj.at_1st and not self.mqtt_clt.msg["first_switch"]:   # 如果物体当前位置在1号对管处,并且当前接收到的mqtt消息为1号对管无遮挡时,将物体当前位置改为处于1,2号对管之间
                        self.obj_pos = PosObj.between_1st_and_2nd
                    else:   # 否则,cnt_except自加1
                        print("1号对管处位置有误!")
                        cnt_except += 1
                    # self.obj_pos = PosObj.at_1st if self.mqtt_clt.msg["first_switch"] else PosObj.between_1st_and_2nd
                elif "second_switch" in self.mqtt_clt.msg:  # 如果接收到的是2号对管的消息
                    if self.obj_pos == PosObj.between_1st_and_2nd and self.mqtt_clt.msg["second_switch"]:   # 如果物体当前位置在1,2号对管之间,并且当前接收到的mqtt消息为2号对管有遮挡时,将物体当前位置改为处于2号对管处
                        self.obj_pos = PosObj.at_2nd
                    elif self.obj_pos == PosObj.at_2nd and not self.mqtt_clt.msg["second_switch"]:  # 如果物体当前位置在2号对管处,并且当前接收到的mqtt消息为2号对管处无遮挡时,将物体当前位置改为处于2,3号对管之间
                        self.obj_pos = PosObj.between_2nd_and_3rd
                    else:   # 否则,cnt_except自加1
                        print("2号对管处位置有误!")
                        cnt_except += 1
                    # self.obj_pos = PosObj.at_2nd if self.mqtt_clt.msg["second_switch"] else PosObj.between_2nd_and_3rd
                elif "third_switch" in self.mqtt_clt.msg:   # 如果接收到的是3号对管的消息
                    if self.obj_pos == PosObj.between_2nd_and_3rd and self.mqtt_clt.msg["third_switch"]:    # 如果物体当前位置在2,3号对管之间,并且当前接收到的mqtt消息为3号对管有遮挡,将物体当前位置改为处于3号对管处
                        self.obj_pos = PosObj.at_3rd
                    elif self.obj_pos == PosObj.at_3rd and not self.mqtt_clt.msg["third_switch"]:   # 如果物体当前位置在3号对管处,并且当前接收到的mqtt消息为3号对管处无遮挡时,将物体当前位置改为处于3号光电对管之后
                        self.obj_pos = PosObj.beyond_3rd
                    else:   # 否则,cnt_except自加1
                        print("3号对管处位置有误!")
                        cnt_except += 1
                    # self.obj_pos = PosObj.at_3rd if self.mqtt_clt.msg["third_switch"] else PosObj.beyond_3rd
                self.mqtt_clt.msg = {}  # 清空mqtt接收到的消息
            self.state_machine()    # 触发状态机

    def handle_timer_statck_rod(self):
        """
        functions:对上货杆的状态进行分情况讨论:
        如果当前上货杆状态为推出,说明上货杆已经完全推出,需要令上货杆拉回;
        否则,如果上货杆状态为拉回,说明上货杆已经完全拉回,需要将上货杆的状态改为停止
        上货之后0.5s结束
        """
        if self.stat_stack_rod == StateRod.push:
            print("上货杆已推出")
            # 发送将第一个杆(货杆)拉回的消息 然后设置为pull状态
            self.mqtt_clt.control_device("rod_control", "first_pull")
            self.stat_stack_rod = StateRod.pull
            ####################################################
            # 设置一个再次调用上货杆的定时器 2s后再次调用
            self.timer_stack_rod = threading.Timer(0.5, self.handle_timer_statck_rod) # 原3.5s
            self.timer_stack_rod.start()
        elif self.stat_stack_rod == StateRod.pull:
            print("上货杆已拉回")
            self.stat_stack_rod = StateRod.stop
        


    def handle_timer_classify_rod(self):
        """
        functions:对分类杆的状态进行分情况讨论:
        如果当前分类杆的状态为推出,说明分类杆已完全推出,需要让相应的分类杆拉回
        否则,如果当前分类杆的状态为拉回,说明分类杆已完全拉回,需要重置分类杆相关成员并令上货杆推出
        调用后0.5s重置
        """
        if self.stat_classify_rod == StateRod.push:
            # 根据"替身变量"确定拉回相应的分类杆
            str_classify_rod_cmd = ""
            if self.classify_rod_act_num_temp == 2:
                str_classify_rod_cmd = "second"
            elif self.classify_rod_act_num_temp == 3:
                str_classify_rod_cmd = "third"
            elif self.classify_rod_act_num_temp == 4:
                str_classify_rod_cmd = "fourth"
            str_classify_rod_cmd += "_pull"
            print("str_classify_rod_cmd:", str_classify_rod_cmd)
            self.mqtt_clt.control_device("rod_control", str_classify_rod_cmd)
            self.stat_classify_rod = StateRod.pull  # 分类杆状态变为拉回
            ####################################################
            # 启动分类杆动作相关定时器 
            self.timer_classify_rod = threading.Timer(0.5, self.handle_timer_classify_rod) # 原3s
            self.timer_classify_rod.start()
        elif self.stat_classify_rod == StateRod.pull:
            print("分类杆已拉回")
            self.classify_rod_act_num = 1   # 当前不需要分类杆动作
            self.stat_classify_rod = StateRod.stop  # 分类杆状态为停止
            ####################################################
            # 拉回后就再次上货 
            self.mqtt_clt.control_device("rod_control", "first_push")
            self.stat_stack_rod = StateRod.push
            # 上货杆在分类结束后立即上货
            self.timer_stack_rod = threading.Timer(0.5, self.handle_timer_statck_rod)
            self.timer_stack_rod.start()

    def state_machine(self):
        """
        functions:以状态机的方法通过物体当前位置以及将要推出的分类杆的编号控制分类杆/上货杆推出,并对相应的状态成员变量进行重设
        """
        if self.obj_pos != PosObj.before_1st and self.obj_pos != PosObj.at_1st:   # 在物体当前位置不在1号对管之前时才进行如下操作
            if self.classify_rod_act_num == 2:  # 当需要2号推杆动作的时候
                if self.obj_pos == PosObj.between_1st_and_2nd:  # 当物体当前位置处于1,2号光电对管之间时
                    # 推出2号推杆并启动分类杆相关定时器(为了完成后续的动作)
                    self.mqtt_clt.control_device("rod_control", "second_push")
                    print("2号推杆推出")
                    self.stat_classify_rod = StateRod.push
                    ####################################################
                    # 分类杆推出0.25s后执行pull函数，再经过0.25s后调用分类杆函数将分类杆重置
                    self.timer_classify_rod = threading.Timer(0.3, self.handle_timer_classify_rod) # 3
                    self.timer_classify_rod.start()
                    # 用"替身变量"替代分类杆动作编号,并将后者重设为无效
                    self.classify_rod_act_num_temp = self.classify_rod_act_num
                    self.classify_rod_act_num = 1
                    self.obj_pos = PosObj.before_1st    # 将物体当前位置重设为处于1号光电对管之前
            elif self.classify_rod_act_num == 3:    # 当需要3号推杆动作的时候
                if self.obj_pos == PosObj.between_2nd_and_3rd:  # 物体当前位置处于2,3号光电对管之间时
                    # 推出3号推杆并启动分类杆相关定时器(为了完成后续的动作)
                    self.mqtt_clt.control_device("rod_control", "third_push")
                    print("3号推杆推出")
                    self.stat_classify_rod = StateRod.push
                    ####################################################
                    self.timer_classify_rod = threading.Timer(0.3, self.handle_timer_classify_rod) # 3
                    self.timer_classify_rod.start()
                    # 用"替身变量"替代分类杆动作编号,并将后者重设为无效
                    self.classify_rod_act_num_temp = self.classify_rod_act_num
                    self.classify_rod_act_num = 1
                    self.obj_pos = PosObj.before_1st    # 将物体当前位置重设为处于1号光电对管之前
            elif self.classify_rod_act_num == 4:    # 当需要4号推杆动作的时候
                if self.obj_pos == PosObj.beyond_3rd:   # 当物体当前位置处于3号光电对管之后时
                    # 推出4号推杆并启动分类杆相关定时器(为了完成后续的动作)
                    self.mqtt_clt.control_device("rod_control", "fourth_push")
                    print("4号推杆推出")
                    self.stat_classify_rod = StateRod.push
                    #################################################### 
                    self.timer_classify_rod = threading.Timer(0.3, self.handle_timer_classify_rod) # 3
                    self.timer_classify_rod.start()
                    # 用"替身变量"替代分类杆动作编号,并将后者重设为无效
                    self.classify_rod_act_num_temp = self.classify_rod_act_num
                    self.classify_rod_act_num = 1
                    self.obj_pos = PosObj.before_1st    # 将物体当前位置重设为处于1号光电对管之前
            else:   # 当不需要任何推杆动作的时候
                if self.obj_pos == PosObj.beyond_3rd:   # 当物体当前位置处于3号光电对管之后时
                    self.obj_pos = PosObj.before_1st    # 将物体当前位置重设为处于1号光电对管之前
                    # 推出1号推杆并启动上货杆相关定时器(为了完成后续的动作)
                    # self.mqtt_clt.control_device("rod_control", "first_push")
                    # self.stat_stack_rod = StateRod.push
                    # #################################################### 
                    # self.timer_stack_rod = threading.Timer(0.5, self.handle_timer_statck_rod) # 3
                    # self.timer_stack_rod.start()

if __name__ == "__main__":
    fs_iiota = FS_IIOTA("127.0.0.1", "http://127.0.0.1:8088/aisim_tf_pre")    # 构造类FS_IIOTA的对象
    # FS_IIOTA("127.0.0.1", "http://127.0.0.1:8088/aitkit_cls_pre", 100)
    fs_iiota.handle_mqtt_json_msg(5)    # 调用成员函数处理通过Mqtt发来的json消息