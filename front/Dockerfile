# 阶段 1: 构建阶段（统一FROM和AS大小写，消除警告）
# 改回官方Node镜像，通过npm源加速（避免阿里云镜像授权问题）
FROM node:18-alpine AS build-stage

# 解决Alpine镜像依赖/网络问题（国内源加速）
# 关键修复1：动态匹配Alpine版本 + 优先HTTP源 + 增加apk update
RUN echo "http://mirrors.aliyun.com/alpine/v$(cat /etc/alpine-release | cut -d'.' -f1,2)/main/" > /etc/apk/repositories \
    && echo "http://mirrors.aliyun.com/alpine/v$(cat /etc/alpine-release | cut -d'.' -f1,2)/community/" >> /etc/apk/repositories \
    && apk update --no-cache \
    && apk add --no-cache git
ENV NODE_OPTIONS=--openssl-legacy-provider

# 设置工作目录
WORKDIR /app

# 先复制依赖文件（利用Docker缓存，修改代码不重新装依赖）
COPY package*.json ./

# 清理缓存 + 国内源安装依赖（避免npm install失败）
# 关键修复2：移除无效的disturl配置，保留核心的registry配置
RUN npm cache clean --force \
    && npm config set registry https://registry.npmmirror.com \
    && npm install --force --no-fund --no-audit

# 复制所有前端代码
COPY . .

# 打包Vue项目（生产环境）
RUN npm run build

# 阶段 2: 运行阶段 (使用 Nginx)
# 改回官方Nginx镜像，避免阿里云镜像授权问题
FROM nginx:stable-alpine AS production-stage

# 核心修复：复制路径从/dist → /app/dist（Vue打包默认输出到工作目录下的dist）
COPY --from=build-stage /app/dist /usr/share/nginx/html

# （可选）添加自定义Nginx配置，解决Vue Router history模式刷新404
# COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口，源端口8080
EXPOSE 60111 

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]