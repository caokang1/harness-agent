package com.example.shop.report.mapper;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface RefundDailyMapper {

    @Update("update refund_daily set refund_count = refund_count + 1 where day = #{day}")
    int increase(@Param("day") String day);

    @Insert("insert into refund_daily (day, refund_count) values (#{day}, 1)")
    int create(@Param("day") String day);
}
