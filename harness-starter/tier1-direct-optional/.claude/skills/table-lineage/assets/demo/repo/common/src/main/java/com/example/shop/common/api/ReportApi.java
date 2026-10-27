package com.example.shop.common.api;

import com.example.shop.common.dto.DailySalesDTO;
import com.example.shop.common.dto.MemberSalesDTO;
import java.util.List;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(name = "report-service", path = "/api/report")
public interface ReportApi {

    @GetMapping("/daily")
    List<DailySalesDTO> daily(@RequestParam("day") String day);

    @GetMapping("/member")
    List<MemberSalesDTO> memberSales(@RequestParam("month") String month);
}
