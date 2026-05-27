# coding: utf-8
import os
import urllib
import time
import joblib  # 用于保存/加载模型
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split

# ====================== 核心修改：模型保存路径改为 back/models ======================
# 获取当前文件所在目录（src 目录）
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取 back 目录（src 的父目录）
BACK_DIR = os.path.dirname(CURRENT_DIR)
# 模型保存的根目录（嵌套目录：back -> models）
MODEL_DIR = os.path.join(BACK_DIR, "models")  # 自动适配Windows/Linux路径分隔符
# TF-IDF向量器保存路径
VECTORIZER_PATH = os.path.join(MODEL_DIR, "tfidf_vectorizer.joblib")
# 逻辑回归模型保存路径
LR_MODEL_PATH = os.path.join(MODEL_DIR, "lr_model.joblib")

# 全局变量，用于缓存模型和向量化器
_vectorizer = None
_lr_model = None

# 获取文本中的请求列表
def get_query_list(filename):
    # 使用相对路径，相对于当前文件所在目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, filename)
    try:
        with open(filepath, 'r', encoding='UTF-8') as f:
            data = f.readlines()
    except FileNotFoundError:
        print(f"错误：找不到文件 {filepath}")
        return []
    
    query_list = []
    for d in data:
        d = d.strip()
        if d:
            d = str(urllib.parse.unquote(d))
            query_list.append(d)
    return list(set(query_list))

# 生成3-gram特征
def get_ngrams(query):
    tempQuery = str(query)
    ngrams = []
    for i in range(0, len(tempQuery)-2):
        ngrams.append(tempQuery[i:i+3])
    return ngrams

# 确保 get_ngrams 函数可以被 joblib 序列化
__all__ = ['predict_http_request', 'get_ngrams']

# 解析HTTP请求报文
def parse_http_request(http_request):
    lines = http_request.strip().split('\n')
    request_parts = []
    if lines:
        request_parts.append(lines[0].strip())
    for line in lines[1:]:
        line = line.strip()
        if line:
            request_parts.append(line)
    full_request = ' '.join(request_parts)
    return full_request

# 保存模型函数（适配嵌套目录）
def save_model(vectorizer, lr_model):
    """保存TF-IDF向量器和逻辑回归模型到 back/models 目录"""
    # 创建嵌套目录（如果不存在），exist_ok=True避免重复创建报错
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    # 保存前临时移除tokenizer，因为自定义函数无法被序列化
    temp_tokenizer = vectorizer.tokenizer
    vectorizer.tokenizer = None
    
    # 保存向量器和模型
    joblib.dump(vectorizer, VECTORIZER_PATH)
    joblib.dump(lr_model, LR_MODEL_PATH)
    
    # 恢复tokenizer
    vectorizer.tokenizer = temp_tokenizer
    
    print(f"✅ 模型已保存到 {os.path.abspath(MODEL_DIR)} 文件夹")  # 打印绝对路径，更清晰

# 加载模型函数
def load_saved_model():
    """加载 back/models 目录下保存的模型，返回(vectorizer, lr_model)"""
    try:
        vectorizer = joblib.load(VECTORIZER_PATH)
        lr_model = joblib.load(LR_MODEL_PATH)
        
        # 加载后重新设置tokenizer
        vectorizer.tokenizer = get_ngrams
        
        print(f"✅ 成功加载本地模型（路径：{os.path.abspath(MODEL_DIR)}）")
        return vectorizer, lr_model
    except FileNotFoundError:
        print("⚠️  未找到保存的模型（路径：{}），将重新训练...".format(os.path.abspath(MODEL_DIR)))
        return None, None
    except Exception as e:
        print(f"⚠️  加载模型失败：{str(e)}，将重新训练...")
        return None, None

# 初始化模型和向量化器
def init_model():
    """
    初始化模型和向量化器，只执行一次
    """
    global _vectorizer, _lr_model
    
    if _vectorizer is not None and _lr_model is not None:
        return _vectorizer, _lr_model
    
    # 尝试加载本地保存的模型
    vectorizer, lr_model = load_saved_model()
    
    # 如果没有保存的模型，则训练并保存
    if vectorizer is None or lr_model is None:
        # 加载数据
        good_query_list = get_query_list('goodqueries.txt')
        bad_query_list = get_query_list('badqueries.txt')
        
        if len(good_query_list) == 0 or len(bad_query_list) == 0:
            print("❌ 正常/恶意请求样本为空，无法训练模型")
            return None, None
        
        print(f"正常请求数量: {len(good_query_list)}")
        print(f"恶意请求数量: {len(bad_query_list)}")

        # 数据预处理
        good_y = [0 for _ in range(len(good_query_list))]
        bad_y = [1 for _ in range(len(bad_query_list))]
        
        queries = bad_query_list + good_query_list
        y = bad_y + good_y

        # 特征工程
        # 使用 lambda 函数包装 get_ngrams，确保可以被序列化
        vectorizer = TfidfVectorizer(tokenizer=lambda x: get_ngrams(x))
        X = vectorizer.fit_transform(queries)
        print(f"特征矩阵形状: {X.shape}")

        # 模型训练
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=20, random_state=42)
        lr_model = LogisticRegression(max_iter=1000)
        lr_model.fit(X_train, y_train)

        # 测试模型准确度
        accuracy = lr_model.score(X_test, y_test)
        print(f'模型的准确度: {accuracy:.4f}\n')

        # 保存训练好的模型
        save_model(vectorizer, lr_model)
    
    # 更新全局变量
    _vectorizer = vectorizer
    _lr_model = lr_model
    
    return vectorizer, lr_model

# 预测单个HTTP请求
def predict_http_request(http_request):
    """
    预测单个HTTP请求是否为恶意
    
    Args:
        http_request: str - 完整的HTTP请求报文
    
    Returns:
        dict - 包含预测结果和概率
    """
    global _vectorizer, _lr_model
    
    # 确保模型已初始化
    if _vectorizer is None or _lr_model is None:
        init_model()
    
    # 解析HTTP请求
    parsed_request = parse_http_request(http_request)
    
    # 进行预测
    X_predict = _vectorizer.transform([parsed_request])
    prediction = _lr_model.predict(X_predict)[0]
    result = '正常请求' if prediction == 0 else '恶意请求'
    
    # 获取预测概率
    prob = _lr_model.predict_proba(X_predict)[0]
    
    return {
        "预测结果": result,
        "置信度": round(prob[prediction], 4),
        "正常请求概率": round(prob[0], 4),
        "恶意请求概率": round(prob[1], 4)
    }

# 交互式预测的函数
def interactive_predict():
    """
    交互式预测函数，支持多次输入
    """
    # 初始化模型
    init_model()
    
    print("="*50)
    print("HTTP请求恶意检测系统")
    print("使用说明：")
    print("1. 输入完整的HTTP请求报文")
    print("2. 输入完成后，按两次连续空行提交")
    print("3. 输入'exit'或'quit'退出程序")
    print("="*50)
    
    while True:
        print("\n请输入HTTP请求报文（输入'exit'或'quit'退出）：")
        
        # 读取用户输入的HTTP请求
        http_request = []
        empty_line_count = 0
        while True:
            try:
                line = input()
                
                # 检查是否退出
                if line.strip().lower() in ['exit', 'quit']:
                    print("\n👋 程序已退出")
                    return
                
                # 检查连续空行
                if not line.strip():
                    empty_line_count += 1
                    if empty_line_count == 2:
                        break
                else:
                    empty_line_count = 0
                
                http_request.append(line)
            except KeyboardInterrupt:
                print("\n\n👋 用户中断输入，程序退出")
                return
            except EOFError:
                print("\n\n👋 输入结束，程序退出")
                return
        
        # 合并输入的请求
        full_request = '\n'.join(http_request)
        
        if not full_request.strip():
            print("⚠️  输入不能为空，请重新输入！")
            continue
        
        # 进行预测
        result = predict_http_request(full_request)
        
        # 输出结果
        print("\n" + "="*50)
        print(f"预测结果: {result['预测结果']}")
        print(f"置信度: {result['置信度']}")
        print(f"正常请求概率: {result['正常请求概率']}")
        print(f"恶意请求概率: {result['恶意请求概率']}")
        print("="*50)

# 加载/训练模型并进行预测的函数（兼容旧版本）
def load_model_and_predict():
    """
    兼容旧版本的函数，调用新的交互式预测函数
    """
    interactive_predict()

# 主函数
if __name__ == '__main__':
    interactive_predict()