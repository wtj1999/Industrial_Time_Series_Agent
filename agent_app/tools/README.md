
sundial 模型
 - 输出形状：(batch_size, forecast_length, num_samples) # 批次大小，预测长度，样本数
toto-2.0-2.5B 模型
 - 输出形状：(9, batch, n_variates, horizon) #  分位数，批次大小，变量数，预测长度
timer-s1
 - 输出形状：(batch_size x quantile_num(9) x forecast_length) # 批次大小，分位数，预测长度

chronos-2 模型、tirex-1.1-gifteval模型、timerfm模型、moirai-2.0-r-small模型
 - 输出形状：(quantile_num(9) x forecast_length) # 分位数，预测长度

## 接口文档一
    url:http://10.2.128.43:19053/time/seriesPredict
    data:{
        "model":"sundial",  # toto-2,sundial
        "dataList":[0.9611527359907225...],
        "predictionLength":8

    }
## 接口文档二
    url:http://10.2.128.43:19054/time/seriesPredict
    data:{
        "model":"sundial",  # chronos-2,timesfm-2.5,moirai-2.0-R-small,timer-s1,tirex-1.1-gifteval
        "dataList":[0.9611527359907225...],
        "predictionLength":8
    }

## 返回参数
    response = {
                "code": "success", 
                "message": "预测成功",
                "predict_data_result": predict_data_result,
                "model": model
            }






