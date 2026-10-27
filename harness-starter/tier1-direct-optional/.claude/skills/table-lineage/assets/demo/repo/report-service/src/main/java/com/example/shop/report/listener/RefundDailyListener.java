package com.example.shop.report.listener;

import com.example.shop.report.constants.ReportTopics;
import com.example.shop.report.mapper.RefundDailyMapper;
import javax.annotation.Resource;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class RefundDailyListener {

    @Resource
    private RefundDailyMapper refundDailyMapper;

    @KafkaListener(topics = ReportTopics.REFUND, groupId = "report-refund-daily")
    public void onMessage(String json) {
        String day = json.substring(0, 10);
        if (refundDailyMapper.increase(day) == 0) {
            refundDailyMapper.create(day);
        }
    }
}
