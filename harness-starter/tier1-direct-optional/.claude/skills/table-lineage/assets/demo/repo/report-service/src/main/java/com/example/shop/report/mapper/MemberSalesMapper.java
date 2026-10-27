package com.example.shop.report.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.shop.report.entity.MemberSales;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Param;

public interface MemberSalesMapper extends BaseMapper<MemberSales> {

    @Delete("delete from member_sales where month = #{month}")
    int deleteByMonth(@Param("month") String month);
}
