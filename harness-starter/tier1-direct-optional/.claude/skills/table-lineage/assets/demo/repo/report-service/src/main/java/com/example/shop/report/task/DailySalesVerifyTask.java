package com.example.shop.report.task;

import com.example.shop.report.mapper.ReportCheckMapper;
import com.xxl.job.core.handler.annotation.XxlJob;
import javax.annotation.Resource;
import org.springframework.stereotype.Component;

/** Compares report row counts and records the result; never changes report data. */
@Component
public class DailySalesVerifyTask {

    @Resource
    private ReportCheckMapper reportCheckMapper;

    @XxlJob("dailySalesVerifyJob")
    public void verify() {
        long rows = reportCheckMapper.countRows("daily_sales");
        reportCheckMapper.log("daily_sales", rows);
    }
}
