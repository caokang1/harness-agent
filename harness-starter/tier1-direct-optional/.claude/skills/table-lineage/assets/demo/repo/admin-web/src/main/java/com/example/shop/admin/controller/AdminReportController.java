package com.example.shop.admin.controller;

import com.example.shop.common.api.ReportApi;
import com.example.shop.common.dto.DailySalesDTO;
import com.example.shop.common.dto.MemberSalesDTO;
import java.util.List;
import javax.annotation.Resource;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/admin/report")
public class AdminReportController {

    @Resource
    private ReportApi reportApi;

    @GetMapping("/daily")
    public List<DailySalesDTO> daily(@RequestParam("day") String day) {
        return reportApi.daily(day);
    }

    @GetMapping("/member")
    public List<MemberSalesDTO> member(@RequestParam("month") String month) {
        return reportApi.memberSales(month);
    }
}
