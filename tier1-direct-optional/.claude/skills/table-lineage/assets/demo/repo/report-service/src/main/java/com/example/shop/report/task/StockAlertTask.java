package com.example.shop.report.task;

import com.example.shop.common.api.StockApi;
import com.example.shop.common.dto.StockDTO;
import com.example.shop.report.entity.AlertRule;
import com.example.shop.report.mapper.AlertRuleMapper;
import com.example.shop.report.mapper.StockAlertMapper;
import com.xxl.job.core.handler.annotation.XxlJob;
import java.util.List;
import javax.annotation.Resource;
import org.springframework.stereotype.Component;

@Component
public class StockAlertTask {

    @Resource
    private AlertRuleMapper alertRuleMapper;
    @Resource
    private StockAlertMapper stockAlertMapper;
    @Resource
    private StockApi stockApi;

    @XxlJob("stockAlertJob")
    public void run() {
        for (AlertRule rule : alertRuleMapper.selectList(null)) {
            List<StockDTO> low = stockApi.listLowStock(rule.getThreshold());
            stockAlertMapper.insertAlerts(rule.getId(), low);
        }
    }
}
