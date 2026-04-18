import time
import requests
import re
import json
from lxml import html
from demo import excel_demo

class BilibiliSpider:
    def __init__(self):
        # 专区映射表（提示词列表）
        self.from_region = {
            '影视': '1001', '娱乐': '1002', '音乐': '1003', '舞蹈': '1004',
            '动画': '1005', '绘画': '1006', '鬼畜': '1007', '游戏': '1008',
            '资讯': '1009', '知识': '1010', '人工智能': '1011', '科技数码': '1012',
            '汽车': '1013', '时尚美妆': '1014', '家装房产': '1015', '户外潮流': '1016',
            '健身': '1017', '体育运动': '1018', '手工': '1019', '美食': '1020',
            '小剧场': '1021', '旅游出行': '1022', '三农': '1023', '动物': '1024',
            '亲子': '1025', '健康': '1026', '情感': '1027', 'vlog': '1029',
            '生活兴趣': '1030', '生活经验': '1031',
        }
        self.headers = {
            'referer': 'https://www.bilibili.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0',
        }
        self.keyword = None          # 当前选择的专区名称
        self.cookies = {
            'buvid3': '2183E43D-1652-F039-1AD4-984B9B3910C734542infoc',
        }
        self.params = {
            'request_cnt': '15',
            'from_region': None,     # 初始为None，选择专区后赋值
        }
        self.excel = excel_demo.Excel()
        self.sheet = self.excel.get_active_sheet()  # 获取默认工作表
        self.sheet.title = "数据表"  # 工作表，可重命名
        self.excel.append_row(self.sheet,["标题", "作者", "播放数", "弹幕数", "点赞数", "硬币数", "收藏数", "转发数", "发布时间", "时长", "分区"])

    def show_keyword_list(self):
        """显示所有可选的专区列表（提示词列表）"""
        print("\n========== 可选的B站专区 ==========")
        for idx, name in enumerate(self.from_region.keys(), 1):
            print(f"{idx:2d}. {name}")
        print("===================================")

    def select_keyword(self):
        """让用户选择专区，返回专区名称和对应的代码"""
        while True:
            self.show_keyword_list()
            choice = input("请输入专区序号或名称（输入0退出程序）: ").strip()
            if choice == '0':
                return None, None
            # 尝试按序号选择
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(self.from_region):
                    name = list(self.from_region.keys())[idx-1]
                    return name, self.from_region[name]
                else:
                    print("序号超出范围，请重新输入。")
                    continue
            # 尝试按名称匹配
            if choice in self.from_region:
                return choice, self.from_region[choice]
            else:
                print("未找到该专区，请重新输入。")

    def extract_coin_and_favorite(self, html_content):
        """从视频详情页提取硬币、收藏、转发数"""
        tree = html.fromstring(html_content)
        script_elements = tree.xpath('//script[contains(text(), "coin")]')
        for script in script_elements:
            script_text = script.text
            if script_text and '"coin"' in script_text and '"favorite"' in script_text:
                match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', script_text, re.DOTALL)
                if match:
                    data = json.loads(match.group(1))
                    stat = data.get('videoData', {}).get('stat', {})
                    coin = stat.get('coin')
                    favorite = stat.get('favorite')
                    share = stat.get('share')
                    return coin, favorite, share
        return None, None, None

    def get_data(self, keyword, region_code, max_pages=1):
        """
        爬取指定专区的视频数据
        :param keyword: 专区名称（用于文件名）
        :param region_code: 专区代码
        :param max_pages: 最大页数（默认20页）
        :return: 爬取的数据行列表
        """
        print(f"\n开始爬取【{keyword}】专区，共 {max_pages} 页...")
        self.params['from_region'] = region_code
        all_data = []

        for page_num in range(1, max_pages + 1):
            self.params['display_id'] = f'{page_num}'
            try:
                resp = requests.get(
                    'https://api.bilibili.com/x/web-interface/region/feed/rcmd',
                    params=self.params,
                    headers=self.headers,
                    cookies=self.cookies,
                )
                resp.raise_for_status()
                data_json = resp.json()
            except Exception as e:
                print(f"请求第 {page_num} 页失败：{e}")
                continue

            archives = data_json.get('data', {}).get('archives', [])
            if not archives:
                print(f"第 {page_num} 页无数据，停止爬取。")
                break

            for i, item in enumerate(archives):
                bvid = item['bvid']
                # 获取详情页以提取硬币、收藏、转发
                try:
                    detail_resp = requests.get(f'https://www.bilibili.com/video/{bvid}/', headers=self.headers)
                    detail_resp.raise_for_status()
                    detail_html = detail_resp.text
                except Exception as e:
                    print(f"获取视频 {bvid} 详情页失败：{e}")
                    coin_count = favorite_count = share = 0
                else:
                    coin_count, favorite_count, share = self.extract_coin_and_favorite(detail_html)
                    # 处理 None 值
                    coin_count = coin_count if coin_count is not None else 0
                    favorite_count = favorite_count if favorite_count is not None else 0
                    share = share if share is not None else 0

                title = item['title']
                author = item['author']['name']
                view_count = item['stat']['view']
                danmaku_count = item['stat']['danmaku']
                like_count = item['stat']['like']
                pub_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['pubdate']))
                duration = time.strftime('%H:%M:%S', time.gmtime(item['duration']))

                row = [title, author, view_count, danmaku_count, like_count,
                       coin_count, favorite_count, share, pub_time, duration, keyword]
                all_data.append(row)

                print(f"  第 {page_num} 页 第 {i+1} 个视频 | 标题：{title[:50]}")
                print(f"  UP主：{author} | 播放：{view_count} 弹幕：{danmaku_count} 点赞：{like_count}")
                print(f"  硬币：{coin_count} 收藏：{favorite_count} 转发：{share} | 发布时间：{pub_time} 时长：{duration}")
                print("-" * 60)
        for row in all_data:
            self.excel.append_row(self.sheet, row)
        # 保存到Excel文件
        self.excel.save(f"bilibili_{keyword}专区.xlsx")
        print(f"【{keyword}】专区爬取完成，共获取 {len(all_data)} 条视频数据")

    def run(self, max_pages=1):
        """主运行函数：循环选择专区、爬取、询问是否继续"""
        print("========= B站专区视频爬虫 =========")

        # 是否全部爬取
        all_region = input("是否全部爬取？(y/n): ")
        if all_region.lower() == 'y':
            start_time = time.time()
            for region_name, region_code in self.from_region.items():
                print(f"开始爬取【{region_name}】专区...")
                self.get_data(region_name, region_code, max_pages)
                time.sleep(1)
            elapsed = time.time() - start_time
            print(f"本次爬取耗时 {elapsed:.2f} 秒")
            return

        else:
            while True:
                keyword, region_code = self.select_keyword()
                if keyword is None:   # 用户选择退出
                    print("已退出程序。")
                    break

                # 开始爬取 记录耗时
                start_time = time.time()
                self.get_data(keyword, region_code, max_pages)
                elapsed = time.time() - start_time
                print(f"本次爬取耗时 {elapsed:.2f} 秒")

                # 询问是否继续爬取其他专区
                while True:
                    again = input("\n是否继续爬取其他专区？(y/n): ").strip().lower()
                    if again in ('y', 'yes'):
                        break   # 跳出内层循环，继续外层循环
                    elif again in ('n', 'no'):
                        print("结束程序")
                        return  # 直接结束整个程序
                    else:
                        print("输入无效，请输入 y 或 n。")

if __name__ == '__main__':
    spider = BilibiliSpider()
    # 每页15条视频数据
    spider.run(max_pages=20)
