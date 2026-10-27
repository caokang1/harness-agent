package com.example.shop.report.controller;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.shop.common.api.ReportApi;
import com.example.shop.common.dto.DailySalesDTO;
import com.example.shop.common.dto.MemberSalesDTO;
import com.example.shop.report.entity.MemberSales;
import com.example.shop.report.mapper.DailySalesMapper;
import com.example.shop.report.mapper.MemberSalesMapper;
import java.util.List;
import java.util.stream.Collectors;
import javax.annotation.Resource;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ReportQueryController implements ReportApi {

    @Resource
    private DailySalesMapper dailySalesMapper;
    @Resource
    private MemberSalesMapper memberSalesMapper;

    @Override
    public List<DailySalesDTO> daily(String day) {
        return dailySalesMapper.listByDay(day);
    }

    @Override
    public List<MemberSalesDTO> memberSales(String month) {
        List<MemberSales> rows = memberSalesMapper.selectList(new QueryWrapper<MemberSales>().eq("month", month));
        return rows.stream().map(r -> new MemberSalesDTO()).collect(Collectors.toList());
    }
}
