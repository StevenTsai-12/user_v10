import requests

def get_ip_location(ip_address):
    try:
        url = f"https://ipinfo.io/{ip_address}/json"
        response = requests.get(url)
        data = response.json()

        print("\n📍 查詢結果：")
        print(f"IP 位址：{data.get('ip', '未知')}")
        print(f"城市：{data.get('city', '未知')}")
        print(f"地區：{data.get('region', '未知')}")
        print(f"國家：{data.get('country', '未知')}")
        print(f"位置座標（經緯度）：{data.get('loc', '未知')}")
        print(f"網路業者：{data.get('org', '未知')}")
        print(f"時區：{data.get('timezone', '未知')}")
    except Exception as e:
        print("❌ 查詢失敗：", e)

if __name__ == "__main__":
    ip = input("請輸入 IP 位址：")
    get_ip_location(ip)
