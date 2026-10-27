package com.example.shop.report.controller;

import com.example.shop.report.service.MemberSalesService;
import javax.annotation.Resource;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Called by the scheduler through an HTTP job. */
@RestController
@RequestMapping("/job")
public class MemberSalesJobController {

    @Resource
    private MemberSalesService memberSalesService;

    @PostMapping("/member-sales")
    public void memberSales(@RequestParam("month") String month) {
        memberSalesService.rebuild(month);
    }
}
