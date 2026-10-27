package com.example.shop.report.service;

import com.example.shop.common.api.MemberApi;
import com.example.shop.common.dto.DailySalesDTO;
import com.example.shop.common.dto.MemberDTO;
import com.example.shop.report.entity.MemberSales;
import com.example.shop.report.mapper.DailySalesMapper;
import com.example.shop.report.mapper.MemberSalesMapper;
import java.util.List;
import javax.annotation.Resource;
import org.springframework.stereotype.Service;

@Service
public class MemberSalesService {

    @Resource
    private DailySalesMapper dailySalesMapper;
    @Resource
    private MemberSalesMapper memberSalesMapper;
    @Resource
    private MemberApi memberApi;

    public void rebuild(String month) {
        memberSalesMapper.deleteByMonth(month);
        List<DailySalesDTO> days = dailySalesMapper.listByMonth(month);
        for (DailySalesDTO d : days) {
            MemberDTO member = memberApi.getMember(d.getStoreId());
            MemberSales row = new MemberSales();
            row.setMonth(month);
            row.setMemberId(member.getId());
            row.setMemberName(member.getName());
            row.setAmount(d.getAmount());
            memberSalesMapper.insert(row);
        }
    }
}
